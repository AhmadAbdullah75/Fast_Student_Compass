import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { ExternalLink } from "lucide-react";
import "katex/dist/katex.min.css";

export default function AnswerMarkdown({
  answer,
  turnId,
}: {
  answer: string;
  turnId: string;
}) {
  // Protect code/math blocks from citation rewriting: transform plain text in
  // the Markdown tree rather than replacing characters inside formulas/code.
  function citations() {
    return (tree: any) => {
      function visit(node: any) {
        if (!node.children) return;
        node.children = node.children.flatMap((child: any) => {
          if (child.type !== "text") {
            if (
              !["code", "inlineCode", "link", "math", "inlineMath"].includes(
                child.type,
              )
            )
              visit(child);
            return [child];
          }
          const parts = [];
          const regex = /\[(S\d+)\]/g;
          let last = 0,
            match;
          while ((match = regex.exec(child.value))) {
            if (match.index > last)
              parts.push({
                type: "text",
                value: child.value.slice(last, match.index),
              });
            parts.push({
              type: "link",
              url: `#source-${turnId}-${match[1]}`,
              children: [{ type: "text", value: match[1] }],
            });
            last = regex.lastIndex;
          }
          if (last < child.value.length)
            parts.push({ type: "text", value: child.value.slice(last) });
          return parts;
        });
      }
      visit(tree);
    };
  }
  return (
    <div className="markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, citations]}
        rehypePlugins={[[rehypeKatex, { trust: false }]]}
        components={{
          a: ({ href, children }) =>
            href?.startsWith("#source-") ? (
              <a
                href={href}
                className="inline-citation"
                onClick={(e) => {
                  e.preventDefault();
                  const el = document.getElementById(href.slice(1));
                  if (el) {
                    let parent: HTMLElement | null = el;
                    while (parent) {
                      if (parent instanceof HTMLDetailsElement)
                        parent.open = true;
                      parent = parent.parentElement;
                    }
                    el.scrollIntoView({
                      behavior: matchMedia("(prefers-reduced-motion: reduce)")
                        .matches
                        ? "auto"
                        : "smooth",
                      block: "center",
                    });
                  }
                }}
              >
                {children}
              </a>
            ) : href && /^(https?:|mailto:)/i.test(href) ? (
              <a href={href} target="_blank" rel="noopener noreferrer">
                {children}
                <ExternalLink size={11} />
              </a>
            ) : (
              <span>{children}</span>
            ),
        }}
      >
        {answer}
      </ReactMarkdown>
    </div>
  );
}
