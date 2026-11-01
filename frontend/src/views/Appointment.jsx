import { useId, useState } from 'react'
import { api } from '../api'
import { PublicFooter, PublicHeader } from '../components/PublicLayout'
import Icon from '../components/icons'
import { inputClass } from '../components/styles'
import { Button, ErrorBox, Field, Notice } from '../components/ui'
import { COUNTRIES, DEFAULT_COUNTRY } from '../countries'
import { href } from '../hooks'

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

const NEXT_STEPS = [
  ['mail', 'Te escribimos', 'Un correo o una llamada para coordinar el día y la hora.'],
  ['layers', 'Vemos tus documentos', 'Conversamos sobre los tipos de documento que maneja tu empresa.'],
  ['scan', 'Te mostramos Veriq', 'Cómo lee, verifica y cuándo pide revisión humana.'],
]

/** Prefijo + número. El select nativo queda encima, invisible: al estar cerrado se ve "CL +56". */
function PhoneInput({ country, onCountry, phone, onPhone, invalid }) {
  const id = useId()
  const selected = COUNTRIES.find((c) => c.iso === country)
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-[13px] font-medium text-ink">
        Número de teléfono
      </label>
      <div
        className={`flex h-11 rounded-control border bg-canvas shadow-control transition-[border-color,box-shadow] duration-150 focus-within:border-brand-600 focus-within:ring-[3px] focus-within:ring-brand-600/15 ${
          invalid ? 'border-danger-600/60' : 'border-line-strong hover:border-brand-300'
        }`}
      >
        <div className="relative flex shrink-0 items-center gap-1.5 border-r border-line pr-2 pl-3 text-sm text-ink">
          <span className="font-mono text-[11px] text-subtle">{selected.iso}</span>
          <span className="font-medium tabular">{selected.dial}</span>
          <Icon name="chevronRight" size={14} className="rotate-90 text-subtle" />
          <select
            aria-label="Prefijo del país"
            value={country}
            onChange={(e) => onCountry(e.target.value)}
            className="absolute inset-0 cursor-pointer opacity-0"
          >
            {COUNTRIES.map((c) => (
              <option key={c.iso} value={c.iso}>
                {c.name} ({c.dial})
              </option>
            ))}
          </select>
        </div>
        <input
          id={id}
          type="tel"
          inputMode="tel"
          autoComplete="tel-national"
          placeholder="9 1234 5678"
          value={phone}
          onChange={(e) => onPhone(e.target.value)}
          aria-invalid={invalid || undefined}
          className="min-w-0 flex-1 rounded-r-control bg-transparent px-3 text-base text-ink tabular placeholder:text-subtle focus:outline-none sm:text-sm"
        />
      </div>
      <span className={`mt-1.5 block text-xs ${invalid ? 'text-danger-700' : 'text-subtle'}`}>
        {invalid ? 'Escribe solo los dígitos del número, sin el prefijo.' : `${selected.name} · sin el prefijo`}
      </span>
    </div>
  )
}

/** Página pública: pedir una cita con un email y un teléfono. La reciben los administradores. */
export default function Appointment() {
  const [email, setEmail] = useState('')
  const [country, setCountry] = useState(DEFAULT_COUNTRY)
  const [phone, setPhone] = useState('')
  // Campo trampa: invisible para las personas
  const [trap, setTrap] = useState('')
  const [touched, setTouched] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [sent, setSent] = useState(null)

  const digits = phone.replace(/[\s\-().]/g, '')
  const emailOk = EMAIL.test(email.trim())
  const phoneOk = /^\d{4,15}$/.test(digits)
  const dial = COUNTRIES.find((c) => c.iso === country).dial

  async function submit(e) {
    e.preventDefault()
    setTouched(true)
    if (!emailOk || !phoneOk) return
    setBusy(true)
    setError(null)
    try {
      await api.appointments.create({ email: email.trim(), pais: country, prefijo: dial, telefono: digits, sitio_web: trap })
      setSent({ email: email.trim(), phone: `${dial} ${phone.trim()}` })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <PublicHeader cta={false} />

      <main className="mx-auto grid w-full max-w-[1200px] flex-1 grid-cols-1 gap-12 px-5 py-12 sm:px-8 lg:grid-cols-[minmax(0,1fr)_440px] lg:items-center lg:gap-20 lg:py-20">
        <div className="animate-enter">
          <a
            href={href('')}
            className="group -ml-1 inline-flex h-7 items-center gap-1.5 rounded-md px-1 text-[13px] font-medium text-muted transition-colors hover:text-brand-700"
          >
            <Icon name="arrowLeft" size={15} className="transition-transform duration-150 group-hover:-translate-x-0.5" />
            Volver
          </a>
          <p className="mt-6 text-[12px] font-semibold tracking-[0.1em] text-brand-600 uppercase">Agenda una cita</p>
          <h1 className="mt-3 text-[34px] leading-[1.08] font-semibold tracking-[-0.035em] text-balance text-ink sm:text-[46px]">
            Conversemos sobre los documentos de tu empresa.
          </h1>
          <p className="mt-5 max-w-lg text-[16px] leading-relaxed text-muted">
            Déjanos tu email y tu teléfono. Te contactamos para coordinar una cita y mostrarte cómo Veriq se adapta a tus
            documentos.
          </p>
          <ol className="mt-10 space-y-5">
            {NEXT_STEPS.map(([icon, title, text], i) => (
              <li key={title} className="flex gap-4">
                <span className="v-cut flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-brand-50 text-brand-600 ring-1 ring-brand-600/15 ring-inset">
                  <Icon name={icon} size={18} />
                </span>
                <span>
                  <span className="block text-[15px] font-semibold text-ink">
                    <span className="mr-2 font-mono text-xs font-normal text-subtle">0{i + 1}</span>
                    {title}
                  </span>
                  <span className="block text-sm text-muted">{text}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>

        <section
          aria-label="Formulario para agendar una cita"
          className="animate-enter rounded-[18px] border border-line bg-canvas p-6 shadow-pop [animation-delay:80ms] [animation-fill-mode:backwards] sm:p-8"
        >
          {sent ? (
            <div role="status" className="text-center">
              <span className="v-cut mx-auto flex h-12 w-12 items-center justify-center rounded-[12px] bg-success-50 text-success-600 ring-1 ring-success-600/20 ring-inset">
                <Icon name="checkCircle" size={22} />
              </span>
              <h2 className="mt-5 text-[20px] font-semibold tracking-[-0.02em] text-ink">Recibimos tu solicitud</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted">
                Te contactaremos en <span className="font-medium text-ink">{sent.email}</span> o al{' '}
                <span className="font-medium whitespace-nowrap text-ink tabular">{sent.phone}</span> para agendar la cita.
              </p>
              <a
                href={href('')}
                className="mt-7 inline-flex h-10 items-center gap-2 rounded-control border border-line-strong px-4 text-sm font-medium text-ink shadow-control transition-[border-color,transform] duration-150 hover:border-brand-300 active:scale-[0.97]"
              >
                <Icon name="arrowLeft" size={15} />
                Volver al inicio
              </a>
            </div>
          ) : (
            <form onSubmit={submit} noValidate>
              <h2 className="text-[20px] font-semibold tracking-[-0.02em] text-ink">Tus datos de contacto</h2>
              <p className="mt-1 mb-7 text-[13px] text-muted">Solo los usamos para coordinar la cita.</p>

              <div className="space-y-5">
                <Field label="Email">
                  <input
                    type="email"
                    autoComplete="email"
                    placeholder="nombre@empresa.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value)
                      setError(null)
                    }}
                    aria-invalid={(touched && !emailOk) || undefined}
                    className={`${inputClass} h-11 text-base sm:text-sm ${touched && !emailOk ? 'border-danger-600/60' : ''}`}
                  />
                  {touched && !emailOk && <span className="mt-1.5 block text-xs text-danger-700">Escribe un email válido.</span>}
                </Field>

                <PhoneInput
                  country={country}
                  onCountry={setCountry}
                  phone={phone}
                  onPhone={(value) => {
                    setPhone(value)
                    setError(null)
                  }}
                  invalid={touched && !phoneOk}
                />

                {/* Campo trampa para robots: fuera de la vista y del orden de tabulación */}
                <div aria-hidden="true" className="absolute -left-[9999px] h-px w-px overflow-hidden">
                  <label>
                    Sitio web
                    <input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} />
                  </label>
                </div>

                <ErrorBox message={error} />
                <Button type="submit" icon="calendar" disabled={busy} className="!h-11 w-full">
                  {busy ? 'Enviando…' : 'Agendar una cita'}
                </Button>
                <Notice tone="brand" icon="shield" className="!text-xs">
                  Solo los administradores de Veriq ven esta solicitud.
                </Notice>
              </div>
            </form>
          )}
        </section>
      </main>
      <PublicFooter />
    </div>
  )
}
