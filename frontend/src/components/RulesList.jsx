import { RULE_LABELS } from '../format'

export default function RulesList({ rules }) {
  if (!rules?.length) return null
  return (
    <ul className="divide-y divide-slate-100 rounded-lg ring-1 ring-slate-200">
      {rules.map((r) => {
        const icon = r.passed ? '✓' : r.severity === 'hard' ? '✕' : '!'
        const color = r.passed
          ? 'bg-emerald-100 text-emerald-700'
          : r.severity === 'hard'
            ? 'bg-rose-100 text-rose-700'
            : 'bg-amber-100 text-amber-800'
        return (
          <li key={r.rule} className="flex items-start gap-3 px-3 py-2">
            <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-bold ${color}`}>
              {icon}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-800">{RULE_LABELS[r.rule] ?? r.rule}</p>
              <p className="text-xs text-slate-500">{r.detail}</p>
            </div>
          </li>
        )
      })}
    </ul>
  )
}
