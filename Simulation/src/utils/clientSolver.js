let worker;
let nextRequestId = 1;
const pending = new Map();

function rejectPending(error) {
  for (const { reject } of pending.values()) {
    reject(error);
  }
  pending.clear();
}

function ensureWorker() {
  if (worker) return worker;

  worker = new Worker(new URL('../workers/solverWorker.js', import.meta.url), {
    type: 'module'
  });

  worker.addEventListener('message', (event) => {
    const { type, requestId, progress, detail, result, error } = event.data || {};
    const request = pending.get(requestId);
    if (!request) return;

    if (type === 'progress') {
      request.onProgress?.({ progress, detail });
      return;
    }

    pending.delete(requestId);
    if (type === 'result') {
      request.resolve(result);
    } else {
      request.reject(new Error(error || 'WASM solver calistirilirken hata olustu.'));
    }
  });

  worker.addEventListener('error', (event) => {
    rejectPending(new Error(event.message || 'WASM Web Worker baslatilamadi.'));
    worker?.terminate();
    worker = null;
  });

  return worker;
}

export async function solveWorkbookWithWasm(file, options, onProgress) {
  const requestId = nextRequestId++;
  const workbookBuffer = await file.arrayBuffer();
  const solverWorker = ensureWorker();

  return new Promise((resolve, reject) => {
    pending.set(requestId, { resolve, reject, onProgress });
    solverWorker.postMessage(
      {
        type: 'solve',
        requestId,
        payload: {
          fileName: file.name,
          workbookBuffer,
          options
        }
      },
      [workbookBuffer]
    );
  });
}

export async function solveWorkbookWithServer(file, options) {
  const form = new FormData();
  form.append('file', file);
  form.append('profile', options.profile);
  form.append('articleSelection', options.articleSelection);
  form.append('candidateGroupWidth', String(options.candidateGroupWidth));
  form.append('timeLimit', String(options.timeLimit));

  const response = await fetch('/api/solve', {
    method: 'POST',
    body: form
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Server solver ${response.status} koduyla hata verdi.`);
  }

  return {
    ...payload,
    runtime: {
      ...payload.runtime,
      mode: 'server-native',
      seedRouteOptimizer: payload.runtime?.lkhPath ? 'lkh' : 'cpp',
      lkhAvailable: Boolean(payload.runtime?.lkhPath)
    }
  };
}
