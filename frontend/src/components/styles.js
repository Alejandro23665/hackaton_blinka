/** Clases compartidas de campos de formulario. */
export const inputClass =
  'block h-10 w-full rounded-control border border-line-strong bg-canvas px-3 text-sm text-ink shadow-control transition-[border-color,box-shadow] duration-150 placeholder:text-subtle hover:border-brand-300 focus:border-brand-600 focus:ring-[3px] focus:ring-brand-600/15 focus:outline-none disabled:cursor-not-allowed disabled:bg-surface disabled:text-subtle'

export const textareaClass = inputClass.replace('h-10', 'min-h-[76px] py-2.5 leading-relaxed')
