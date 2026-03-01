export function LoadingIndicator({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-2 px-1 py-1.5">
      <div className="flex items-center gap-1">
        <div className="h-1.5 w-1.5 rounded-full bg-orange-400 animate-bounce [animation-delay:-0.3s]" />
        <div className="h-1.5 w-1.5 rounded-full bg-orange-400 animate-bounce [animation-delay:-0.15s]" />
        <div className="h-1.5 w-1.5 rounded-full bg-orange-400 animate-bounce" />
      </div>
      {message && (
        <span className="text-xs text-slate-400">{message}</span>
      )}
    </div>
  );
}
