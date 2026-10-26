export function BarList({
  title,
  data,
  color = 'bg-lime',
}: {
  title: string
  data: { name: string; count: number }[]
  color?: string
}) {
  const max = Math.max(1, ...data.map((d) => d.count))
  return (
    <div className="sticker p-5">
      <div className="font-fun">{title}</div>
      <div className="mt-3 space-y-2">
        {data.length === 0 && <div className="text-[13px] text-ink/50">暂无数据</div>}
        {data.map((d) => (
          <div key={d.name} className="flex items-center gap-3">
            <div className="w-32 shrink-0 truncate font-mono text-[12.5px]" title={d.name}>
              {d.name}
            </div>
            <div className="h-5 flex-1 overflow-hidden rounded-full border-2 border-ink bg-white">
              <div
                className={`h-full ${color} transition-all duration-500`}
                style={{ width: `${(d.count / max) * 100}%` }}
              />
            </div>
            <div className="w-10 shrink-0 text-right font-mono text-[12.5px] font-bold">{d.count}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
