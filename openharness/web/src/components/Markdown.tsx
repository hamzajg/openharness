import ReactMarkdown from 'react-markdown'

export default function Markdown({ text }: { text: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none">
      <ReactMarkdown>{text}</ReactMarkdown>
    </div>
  )
}
