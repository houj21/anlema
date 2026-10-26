import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { cn } from '@/lib/utils'

function CodeBlock({ lang, code }: { lang: string; code: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
    } catch (e) {
      const ta = document.createElement('textarea')
      ta.value = code
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    setCopied(true)
    setTimeout(() => setCopied(false), 1600)
  }

  const label = lang === 'powershell' ? 'PowerShell' : lang === 'bash' ? 'Bash / zsh' : lang || 'code'

  return (
    <div className="my-4 overflow-hidden rounded-2xl border-[3px] border-ink shadow-stickerSm">
      <div className="flex items-center justify-between bg-ink px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="h-3 w-3 rounded-full bg-pink" />
          <span className="h-3 w-3 rounded-full bg-lime" />
          <span className="h-3 w-3 rounded-full bg-cyan" />
          <span className="ml-2 font-mono text-[12px] text-paper/70">{label}</span>
        </div>
        <button
          onClick={copy}
          className={cn(
            'inline-flex items-center gap-1.5 rounded-lg border-2 border-paper/30 px-2.5 py-1 font-mono text-[12px]',
            'text-paper/90 transition hover:bg-paper/15',
            copied && 'bg-lime text-ink border-lime'
          )}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? '已复制' : '复制'}
        </button>
      </div>
      <SyntaxHighlighter
        language={lang || 'bash'}
        style={vscDarkPlus}
        customStyle={{ margin: 0, padding: '16px', fontSize: '13px', background: '#171310' }}
        wrapLongLines
      >
        {code}
      </SyntaxHighlighter>
    </div>
  )
}

export function MarkdownView({ content }: { content: string }) {
  // 方案里可能带 HTML 注释形式的内部标记（如模板版本），别让用户看到
  const clean = content.replace(/<!--[\s\S]*?-->/g, '')
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code(props: any) {
            const { inline, className, children } = props
            const match = /language-(\w+)/.exec(className || '')
            const code = String(children).replace(/\n$/, '')
            if (inline) {
              return <code className={className}>{children}</code>
            }
            return <CodeBlock lang={match?.[1] || ''} code={code} />
          },
          a(props: any) {
            return <a {...props} target="_blank" rel="noreferrer" />
          },
        }}
      >
        {clean}
      </ReactMarkdown>
    </div>
  )
}
