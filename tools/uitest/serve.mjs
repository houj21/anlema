/* 用 Node 起两个静态服务器，托管 desktop/dist 与 admin/dist，供 run.mjs 冒烟 */
import http from 'node:http'
import fs from 'node:fs'
import path from 'node:path'

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.woff2': 'font/woff2',
  '.json': 'application/json; charset=utf-8',
}

function serve(root, port) {
  http
    .createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || '/').split('?')[0])
      let file = path.join(root, urlPath === '/' ? 'index.html' : urlPath)
      if (!file.startsWith(root)) {
        res.writeHead(403).end()
        return
      }
      if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
        file = path.join(root, 'index.html')
      }
      res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] || 'application/octet-stream' })
      res.end(fs.readFileSync(file))
    })
    .listen(port, '127.0.0.1', () => console.log(`  ${root} -> http://127.0.0.1:${port}/`))
}

const base = path.resolve(import.meta.dirname, '../..')
for (const [dir, port] of [
  [path.join(base, 'desktop/dist'), 5190],
  [path.join(base, 'admin/dist'), 5191],
]) {
  if (!fs.existsSync(dir)) {
    console.error(`缺少 ${dir}，先执行 npm run build`)
    process.exit(1)
  }
  serve(dir, port)
}
console.log('静态服务器已启动，Ctrl+C 结束')
