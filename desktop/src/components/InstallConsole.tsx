import { useEffect, useRef } from 'react'
import { Loader2, Square, Terminal, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export interface LogLine {
  text: string
  kind: 'out' | 'err' | 'sys' | 'ok'
}

export function InstallConsole({
  lines,
  running,
  onStop,
  onClear,
  onClose,
}: {
  lines: LogLine[]
  running: boolean
  onStop: () => void
  onClear: () => void
  onClose: () => void
}) {
  const boxRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = boxRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [lines.length])

  const color = (k: string) =>
    k === 'err'
      ? 'text-pink'
      : k === 'ok'
        ? 'text-lime'
        : k === 'sys'
          ? 'text-cyan'
          : 'text-paper/85'

  return (
    <div className="sticker animate-slideUp overflow-hidden bg-ink">
      <div className="flex items-center justify-between border-b-[3px] border-paper/20 px-4 py-2">
        <div className="flex items-center gap-2 font-mono text-[13px] text-paper">
          {running ? (
            <Loader2 className="h-4 w-4 animate-spin text-lime" />
          ) : (
            <Terminal className="h-4 w-4 text-lime" />
          )}
          <span className="font-bold">安装现场直播</span>
          <span className="text-paper/50">{running ? '正在执行…' : '空闲'}</span>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" className="text-paper hover:bg-paper/10" onClick={onClear}>
            <Trash2 className="h-3.5 w-3.5" /> 清屏
          </Button>
          {running && (
            <Button size="sm" variant="pink" onClick={onStop}>
              <Square className="h-3 w-3" /> 停止
            </Button>
          )}
          <Button size="sm" variant="ghost" className="text-paper hover:bg-paper/10" onClick={onClose}>
            收起
          </Button>
        </div>
      </div>
      <div
        ref={boxRef}
        className="max-h-64 min-h-[140px] overflow-auto bg-[#120F0D] px-4 py-3 font-mono text-[12.5px] leading-[1.7]"
      >
        {lines.length === 0 && (
          <div className="text-paper/40">// 还没有输出。点上面的「一键安装」，日志会出现在这里。</div>
        )}
        {lines.map((l, i) => (
          <div key={i} className={cn('whitespace-pre-wrap break-all', color(l.kind))}>
            {l.text || ' '}
          </div>
        ))}
        {running && (
          <div className="mt-1 inline-block h-4 w-2 animate-pulse bg-lime align-middle" />
        )}
      </div>
    </div>
  )
}
