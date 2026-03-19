import type { AssistantBlock } from "@/lib/assistantContent";

function Heading({ text }: { text: string }) {
  return (
    <h3 className="text-base font-semibold text-zinc-100 mt-3 first:mt-0 mb-1.5">
      {text}
    </h3>
  );
}

function Paragraph({ text }: { text: string }) {
  const parts = text.split("\n\n");
  return (
    <div className="space-y-2 mb-2 last:mb-0">
      {parts.map((chunk, i) => (
        <p key={i} className="text-sm leading-relaxed text-zinc-200 whitespace-pre-wrap break-words">
          {chunk}
        </p>
      ))}
    </div>
  );
}

function ListBlock({ ordered, items }: { ordered: boolean; items: string[] }) {
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag
      className={`mb-2 pl-5 text-sm text-zinc-200 space-y-1 ${
        ordered ? "list-decimal" : "list-disc"
      }`}
    >
      {items.map((item, i) => (
        <li key={i} className="leading-relaxed break-words pl-1">
          {item}
        </li>
      ))}
    </Tag>
  );
}

function CodeBlock({ text, language }: { text: string; language?: string }) {
  return (
    <div className="mb-2 rounded-lg bg-zinc-950 border border-zinc-700/80 overflow-x-auto">
      {language ? (
        <div className="px-3 py-1 text-[10px] uppercase tracking-wider text-zinc-500 border-b border-zinc-800">
          {language}
        </div>
      ) : null}
      <pre className="px-3 py-2.5 text-xs font-mono text-emerald-100/90 whitespace-pre">
        <code>{text}</code>
      </pre>
    </div>
  );
}

function TableBlock({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="mb-2 overflow-x-auto rounded-lg border border-zinc-700/80">
      <table className="w-full text-left text-xs text-zinc-200 border-collapse">
        <thead>
          <tr className="bg-zinc-900/80">
            {headers.map((h, i) => (
              <th
                key={i}
                className="px-3 py-2 font-semibold text-zinc-300 border-b border-zinc-700"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="even:bg-zinc-900/40">
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="px-3 py-2 border-b border-zinc-800 align-top break-words max-w-[12rem]"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Block({ block }: { block: AssistantBlock }) {
  switch (block.type) {
    case "heading":
      return <Heading text={block.text} />;
    case "paragraph":
      return <Paragraph text={block.text} />;
    case "list":
      return <ListBlock ordered={block.ordered} items={block.items} />;
    case "code":
      return <CodeBlock text={block.text} language={block.language} />;
    case "table":
      return <TableBlock headers={block.headers} rows={block.rows} />;
    default:
      return null;
  }
}

export default function AssistantMessageBody({ blocks }: { blocks: AssistantBlock[] }) {
  return (
    <div className="space-y-1">
      {blocks.map((block, i) => (
        <Block key={i} block={block} />
      ))}
    </div>
  );
}
