const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('zlm', {
  info: () => ipcRenderer.invoke('app:info'),
  runScript: (payload) => ipcRenderer.invoke('script:run', payload),
  stopScript: () => ipcRenderer.invoke('script:stop'),
  openExternal: (url) => ipcRenderer.invoke('app:openExternal', url),
  onOutput: (cb) => {
    const handler = (_e, data) => cb(data)
    ipcRenderer.on('script:output', handler)
    return () => ipcRenderer.removeListener('script:output', handler)
  },
  onDone: (cb) => {
    const handler = (_e, data) => cb(data)
    ipcRenderer.on('script:done', handler)
    return () => ipcRenderer.removeListener('script:done', handler)
  },
})
