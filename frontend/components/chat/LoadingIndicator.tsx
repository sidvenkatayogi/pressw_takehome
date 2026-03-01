export function LoadingIndicator() {
  return (
    <div className="flex items-center gap-1.5 px-4 py-2">
      <div className="h-2 w-2 rounded-full bg-orange-400 animate-bounce [animation-delay:-0.3s]" />
      <div className="h-2 w-2 rounded-full bg-orange-400 animate-bounce [animation-delay:-0.15s]" />
      <div className="h-2 w-2 rounded-full bg-orange-400 animate-bounce" />
    </div>
  );
}
