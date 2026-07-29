"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="whitespace-pre-wrap text-foreground/90 text-sm leading-relaxed">{content}</div>;
  }

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // ── Paragraphs ──
        p: ({ children }) => (
          <p className="mb-3 last:mb-0 text-foreground/90 leading-7 text-sm">{children}</p>
        ),

        // ── Bold / Italic ──
        strong: ({ children }) => (
          <strong className="font-bold text-foreground bg-primary/8 px-0.5 rounded">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic text-primary/80">{children}</em>
        ),

        // ── Headings ──
        h1: ({ children }) => (
          <h1 className="text-lg font-black text-foreground mt-5 mb-2 pb-1.5 border-b border-primary/20 flex items-center gap-2">
            <span className="w-1.5 h-5 bg-gradient-to-b from-blue-500 to-indigo-600 rounded-full inline-block" />
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-base font-bold text-foreground mt-4 mb-2 flex items-center gap-2">
            <span className="w-1 h-4 bg-gradient-to-b from-blue-400 to-indigo-500 rounded-full inline-block opacity-80" />
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-sm font-semibold text-primary mt-3 mb-1.5 uppercase tracking-wide">{children}</h3>
        ),
        h4: ({ children }) => (
          <h4 className="text-sm font-semibold text-foreground mt-2 mb-1">{children}</h4>
        ),

        // ── Lists ──
        ul: ({ children }) => (
          <ul className="my-3 space-y-1.5 pl-0">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-3 space-y-1.5 list-decimal pl-5">{children}</ol>
        ),
        li: ({ children }) => (
          <li className="flex items-start gap-2 text-sm text-foreground/90 leading-relaxed">
            <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-gradient-to-br from-blue-500 to-indigo-500" />
            <span>{children}</span>
          </li>
        ),

        // ── Inline Code ──
        code: ({ children, className }) => {
          const isBlock = className?.includes('language-');
          if (isBlock) {
            return (
              <div className="my-3 rounded-xl overflow-hidden border border-border/60 shadow-sm">
                <div className="flex items-center justify-between px-4 py-2 bg-secondary/60 border-b border-border/60">
                  <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase tracking-widest">
                    {className?.replace('language-', '') || 'code'}
                  </span>
                  <div className="flex gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-rose-400/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400/70" />
                    <span className="w-2.5 h-2.5 rounded-full bg-emerald-400/70" />
                  </div>
                </div>
                <pre className="bg-[#0d1117] p-4 overflow-x-auto">
                  <code className="text-[13px] font-mono text-emerald-300 leading-relaxed">{children}</code>
                </pre>
              </div>
            );
          }
          return (
            <code className="bg-blue-500/10 text-blue-400 dark:text-blue-300 px-1.5 py-0.5 rounded-md font-mono text-[12px] border border-blue-500/20">
              {children}
            </code>
          );
        },
        pre: ({ children }) => <>{children}</>,

        // ── Blockquote ──
        blockquote: ({ children }) => (
          <blockquote className="my-3 pl-4 border-l-4 border-gradient-to-b border-blue-500 bg-blue-500/5 py-2 pr-3 rounded-r-xl italic text-foreground/80 text-sm">
            {children}
          </blockquote>
        ),

        // ── Tables ──
        table: ({ children }) => (
          <div className="my-4 overflow-x-auto rounded-xl border border-border/60 shadow-sm">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => (
          <thead className="bg-gradient-to-r from-blue-600/20 to-indigo-600/20 border-b border-border/60">
            {children}
          </thead>
        ),
        tbody: ({ children }) => (
          <tbody className="divide-y divide-border/40 bg-card/60">{children}</tbody>
        ),
        tr: ({ children }) => (
          <tr className="hover:bg-primary/5 transition-colors">{children}</tr>
        ),
        th: ({ children }) => (
          <th className="px-4 py-2.5 text-left text-[11px] font-black uppercase tracking-wider text-primary/80">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="px-4 py-2.5 text-foreground/80 text-sm leading-relaxed">{children}</td>
        ),

        // ── Horizontal Rule ──
        hr: () => (
          <hr className="my-4 border-0 h-px bg-gradient-to-r from-transparent via-primary/20 to-transparent" />
        ),

        // ── Links ──
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 underline underline-offset-2 decoration-blue-500/40 hover:decoration-blue-400 transition-colors"
          >
            {children}
          </a>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
