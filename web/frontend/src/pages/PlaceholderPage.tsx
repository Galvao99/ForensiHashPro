export function PlaceholderPage({ title, message }: { title: string; message: string }) {
  return <div className="app-page"><p className="eyebrow">PLATAFORMA</p><h1>{title}</h1><div className="app-panel"><p>{message}</p></div></div>
}
