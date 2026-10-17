import { RULE_LABELS } from '../format'
import Icon from './icons'

const STYLE = {
  passed: { icon: 'check', className: 'bg-brand-100 text-brand-700' },
  hard: { icon: 'x', className: 'bg-danger-50 text-danger-600' },
  soft: { icon: 'user', className: 'bg-warning-50 text-warning-700' },
}

export default function RulesList({ rules }) {
  if (!rules?.length) return null
  const passed = rules.filter((r) => r.passed).length

  return (
    <div>
      <p className="mb-2 text-xs text-muted">
        {passed} de {rules.length} reglas cumplidas
      </p>
      <ul className="divide-y divide-line overflow-hidden rounded-control border border-line">
        {rules.map((r) => {
          const s = r.passed ? STYLE.passed : STYLE[r.severity] ?? STYLE.hard
          return (
            <li key={r.rule} className={`flex items-start gap-3 px-3 py-2.5 ${r.passed ? '' : 'bg-surface'}`}>
              <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full ${s.className}`}>
                <Icon name={s.icon} size={12} strokeWidth={2.5} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-ink">{RULE_LABELS[r.rule] ?? r.rule}</p>
                <p className="text-xs text-muted">{r.detail}</p>
              </div>
              {!r.passed && (
                <span className="shrink-0 text-[11px] font-medium text-subtle">{r.severity === 'hard' ? 'Bloquea' : 'Escala'}</span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
