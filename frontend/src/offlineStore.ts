export type OfflineOperationType =
  | "service_request.create"
  | "service_request.transition"
  | "incident.create"
  | "incident.update"
  | "maintenance_work_order.create"
  | "maintenance_work_order.transition";

export type LocalSyncOperation = {
  operation_id: string;
  owner_id: string;
  organization_id: string;
  operation_type: OfflineOperationType;
  record_id?: string;
  created_at: string;
  payload: Record<string, unknown>;
  state: "pending" | "conflict";
  last_error?: string;
};

type CachedResponse = {
  key: string;
  owner_id: string;
  organization_id: string;
  stored_at: string;
  value: unknown;
};

type SyncMetadata = {
  key: string;
  last_sync_at: string;
};

const DATABASE_NAME = "oxmaint-offline";
const DATABASE_VERSION = 1;
const RESPONSE_STORE = "responses";
const OPERATION_STORE = "operations";
const METADATA_STORE = "metadata";
const CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;

let databasePromise: Promise<IDBDatabase> | undefined;

function openDatabase(): Promise<IDBDatabase> {
  if (typeof indexedDB === "undefined") {
    return Promise.reject(new Error("Offline storage is not available in this browser."));
  }
  if (databasePromise) return databasePromise;

  const openingPromise = new Promise<IDBDatabase>((resolve, reject) => {
    const opening = indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    opening.onupgradeneeded = () => {
      const database = opening.result;
      if (!database.objectStoreNames.contains(RESPONSE_STORE)) {
        database.createObjectStore(RESPONSE_STORE, { keyPath: "key" });
      }
      if (!database.objectStoreNames.contains(OPERATION_STORE)) {
        const operations = database.createObjectStore(OPERATION_STORE, { keyPath: "operation_id" });
        operations.createIndex("owner_organization", ["owner_id", "organization_id"], { unique: false });
      }
      if (!database.objectStoreNames.contains(METADATA_STORE)) {
        database.createObjectStore(METADATA_STORE, { keyPath: "key" });
      }
    };
    opening.onsuccess = () => {
      opening.result.onversionchange = () => {
        opening.result.close();
        databasePromise = undefined;
      };
      resolve(opening.result);
    };
    opening.onerror = () => reject(opening.error || new Error("Could not open offline storage."));
    opening.onblocked = () => reject(new Error("Offline storage is blocked by another open OxMaint tab."));
  });
  databasePromise = openingPromise;
  void openingPromise.catch(error => {
    databasePromise = undefined;
  });
  return openingPromise;
}

function runTransaction<T>(
  stores: string[],
  operation: (transaction: IDBTransaction) => IDBRequest<T>,
  mode: IDBTransactionMode = "readonly"
): Promise<T> {
  return openDatabase().then(database => new Promise((resolve, reject) => {
    const transaction = database.transaction(stores, mode);
    const request = operation(transaction);
    let result: T | undefined;
    request.onsuccess = () => { result = request.result; };
    request.onerror = () => reject(request.error || new Error("Offline storage request failed."));
    transaction.oncomplete = () => resolve(result as T);
    transaction.onerror = () => reject(transaction.error || new Error("Offline storage transaction failed."));
    transaction.onabort = () => reject(transaction.error || new Error("Offline storage transaction was aborted."));
  }));
}

function responseKey(ownerId: string, organizationId: string, path: string) {
  return `${ownerId}:${organizationId}:${path}`;
}

function metadataKey(ownerId: string, organizationId: string) {
  return `${ownerId}:${organizationId}`;
}

export async function cacheResponse(
  ownerId: string,
  organizationId: string,
  path: string,
  value: unknown
): Promise<void> {
  const record: CachedResponse = {
    key: responseKey(ownerId, organizationId, path),
    owner_id: ownerId,
    organization_id: organizationId,
    stored_at: new Date().toISOString(),
    value,
  };
  await runTransaction([RESPONSE_STORE], transaction =>
    transaction.objectStore(RESPONSE_STORE).put(record)
  );
}

export async function readCachedResponse<T>(
  ownerId: string,
  organizationId: string,
  path: string
): Promise<T | undefined> {
  const record = await runTransaction<CachedResponse | undefined>(
    [RESPONSE_STORE],
    transaction => transaction.objectStore(RESPONSE_STORE).get(
      responseKey(ownerId, organizationId, path)
    )
  );
  if (record) {
    const storedAt = Date.parse(record.stored_at);
    if (!Number.isFinite(storedAt) || Date.now() - storedAt > CACHE_MAX_AGE_MS) {
      await runTransaction([RESPONSE_STORE], transaction =>
        transaction.objectStore(RESPONSE_STORE).delete(
          responseKey(ownerId, organizationId, path)
        )
      );
      return undefined;
    }
  }
  return record?.value as T | undefined;
}

export async function enqueueOperation(
  ownerId: string,
  organizationId: string,
  operationType: OfflineOperationType,
  payload: Record<string, unknown>,
  recordId?: string
): Promise<LocalSyncOperation> {
  const operation: LocalSyncOperation = {
    operation_id: crypto.randomUUID(),
    owner_id: ownerId,
    organization_id: organizationId,
    operation_type: operationType,
    ...(recordId ? { record_id: recordId } : {}),
    created_at: new Date().toISOString(),
    payload,
    state: "pending",
  };
  await runTransaction([OPERATION_STORE], transaction =>
    transaction.objectStore(OPERATION_STORE).add(operation)
  );
  return operation;
}

export async function listOperations(
  ownerId: string,
  organizationId: string
): Promise<LocalSyncOperation[]> {
  const records = await runTransaction<LocalSyncOperation[]>(
    [OPERATION_STORE],
    transaction => transaction.objectStore(OPERATION_STORE)
      .index("owner_organization")
      .getAll(IDBKeyRange.only([ownerId, organizationId]))
  );
  return records.sort((left, right) => left.created_at.localeCompare(right.created_at));
}

export async function removeOperation(operationId: string): Promise<void> {
  await runTransaction([OPERATION_STORE], transaction =>
    transaction.objectStore(OPERATION_STORE).delete(operationId)
  );
}

export async function markOperationConflict(
  operationId: string,
  error: string
): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction([OPERATION_STORE], "readwrite");
    const store = transaction.objectStore(OPERATION_STORE);
    const request = store.get(operationId);
    request.onsuccess = () => {
      if (!request.result) {
        reject(new Error("The queued operation no longer exists."));
        transaction.abort();
        return;
      }
      store.put({ ...request.result, state: "conflict", last_error: error });
    };
    request.onerror = () => reject(request.error || new Error("Could not load the queued operation."));
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not save the synchronization conflict."));
    transaction.onabort = () => reject(transaction.error || new Error("Saving the synchronization conflict was aborted."));
  });
}

export async function retryOperation(operationId: string): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction([OPERATION_STORE], "readwrite");
    const store = transaction.objectStore(OPERATION_STORE);
    const request = store.get(operationId);
    request.onsuccess = () => {
      if (!request.result) {
        reject(new Error("The queued operation no longer exists."));
        transaction.abort();
        return;
      }
      const { last_error: _lastError, ...operation } = request.result;
      store.put({ ...operation, state: "pending" });
    };
    request.onerror = () => reject(request.error || new Error("Could not load the queued operation."));
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not retry the synchronization operation."));
    transaction.onabort = () => reject(transaction.error || new Error("Retrying the synchronization operation was aborted."));
  });
}

export async function getLastSync(
  ownerId: string,
  organizationId: string
): Promise<string | undefined> {
  const record = await runTransaction<SyncMetadata | undefined>(
    [METADATA_STORE],
    transaction => transaction.objectStore(METADATA_STORE).get(
      metadataKey(ownerId, organizationId)
    )
  );
  return record?.last_sync_at;
}

export async function setLastSync(
  ownerId: string,
  organizationId: string,
  lastSyncAt: string
): Promise<void> {
  await runTransaction([METADATA_STORE], transaction =>
    transaction.objectStore(METADATA_STORE).put({
      key: metadataKey(ownerId, organizationId),
      last_sync_at: lastSyncAt,
    })
  );
}

export async function clearCachedResponses(ownerId: string): Promise<void> {
  const database = await openDatabase();
  await new Promise<void>((resolve, reject) => {
    const transaction = database.transaction([RESPONSE_STORE], "readwrite");
    const store = transaction.objectStore(RESPONSE_STORE);
    const request = store.openCursor();
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) return;
      if ((cursor.value as CachedResponse).owner_id === ownerId) cursor.delete();
      cursor.continue();
    };
    request.onerror = () => reject(request.error || new Error("Could not clear offline data."));
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("Could not clear offline data."));
    transaction.onabort = () => reject(transaction.error || new Error("Clearing offline data was aborted."));
  });
}
