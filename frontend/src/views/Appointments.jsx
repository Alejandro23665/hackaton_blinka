import { api } from '../api'
import Icon from '../components/icons'
import { Card, Empty, ErrorBox, Loading, PageHeader } from '../components/ui'
import { countryName } from '../countries'
import { dateTime } from '../format'
import { useLoad } from '../hooks'

function Phone({ cita }) {
  return (
    <a href={`tel:${cita.prefijo}${cita.telefono}`} className="font-medium text-ink tabular hover:text-brand-700">
      {cita.prefijo} {cita.telefono}
    </a>
  )
}

function Email({ cita }) {
  return (
    <a href={`mailto:${cita.email}`} className="font-medium break-all text-ink hover:text-brand-700">
      {cita.email}
    </a>
  )
}

/** Citas pedidas desde la página pública (solo administradores), la más reciente primero. */
export default function Appointments() {
  const citas = useLoad(() => api.appointments.list())
  const list = citas.data

  return (
    <div className="space-y-6 lg:space-y-8">
      <PageHeader
        eyebrow="Administración"
        title="Citas"
        meta="Solicitudes hechas desde la página pública con el botón «Agendar una cita»."
      />
      <Card
        title="Solicitudes"
        subtitle={list ? `${list.length} solicitud${list.length === 1 ? '' : 'es'} · la más reciente primero` : undefined}
      >
        <ErrorBox message={citas.error} />
        {!list && citas.loading && <Loading />}
        {list?.length === 0 && (
          <Empty icon="calendar" title="Aún no hay citas">
            Cuando alguien deje su email y su teléfono en la página pública, aparecerá aquí.
          </Empty>
        )}
        {list?.length > 0 && (
          <>
            {/* Móvil: una tarjeta por solicitud */}
            <ul className="-mx-5 -mb-5 divide-y divide-line border-t border-line sm:-mx-6 sm:-mb-6 md:hidden">
              {list.map((cita) => (
                <li key={cita.id} className="space-y-1.5 px-5 py-4 text-sm sm:px-6">
                  <Email cita={cita} />
                  <p className="flex items-center gap-2">
                    <Icon name="phone" size={14} className="text-subtle" />
                    <Phone cita={cita} />
                    <span className="text-xs text-subtle">{countryName(cita.pais)}</span>
                  </p>
                  <p className="text-xs text-subtle">{dateTime(cita.creado_en)}</p>
                </li>
              ))}
            </ul>

            {/* Escritorio: tabla */}
            <div className="-mx-5 -mb-5 hidden overflow-x-auto border-t border-line sm:-mx-6 sm:-mb-6 md:block">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="bg-surface/60">
                  <tr className="border-b border-line text-[11.5px] tracking-[0.04em] text-subtle uppercase">
                    <th className="py-2.5 pr-3 pl-6 font-semibold">Recibida</th>
                    <th className="px-3 py-2.5 font-semibold">Email</th>
                    <th className="px-3 py-2.5 font-semibold">Teléfono</th>
                    <th className="py-2.5 pr-6 pl-3 font-semibold">País</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {list.map((cita) => (
                    <tr key={cita.id}>
                      <td className="py-3 pr-3 pl-6 whitespace-nowrap text-muted tabular">{dateTime(cita.creado_en)}</td>
                      <td className="px-3 py-3">
                        <Email cita={cita} />
                      </td>
                      <td className="px-3 py-3 whitespace-nowrap">
                        <Phone cita={cita} />
                      </td>
                      <td className="py-3 pr-6 pl-3 whitespace-nowrap text-muted">
                        <span className="mr-2 font-mono text-[11px] text-subtle">{cita.pais}</span>
                        {countryName(cita.pais)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  )
}
