/** Clases compartidas de campos de formulario. */
export const inputClass =
  'block h-10 w-full rounded-control border border-line-strong bg-canvas px-3 text-sm text-ink shadow-control transition-colors placeholder:text-subtle hover:border-brand-300 focus:border-brand-600 focus:ring-4 focus:ring-brand-100 focus:outline-none disabled:bg-surface'

export const textareaClass = inputClass.replace('h-10', 'min-h-[76px] py-2.5 leading-relaxed')
