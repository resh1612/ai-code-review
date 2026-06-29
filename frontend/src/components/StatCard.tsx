interface Props {
  label: string
  value: string | number
  icon?: string
  accent?: string
}

export default function StatCard({ label, value, icon, accent = 'text-indigo-400' }: Props) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/5 p-4 flex items-center gap-4 backdrop-blur-sm">
      {icon && (
        <div className="text-2xl w-10 h-10 flex items-center justify-center rounded-lg bg-white/5">
          {icon}
        </div>
      )}
      <div>
        <p className="text-xs text-slate-500 uppercase tracking-wider font-medium">{label}</p>
        <p className={`text-2xl font-bold mt-0.5 ${accent}`}>{value}</p>
      </div>
    </div>
  )
}
