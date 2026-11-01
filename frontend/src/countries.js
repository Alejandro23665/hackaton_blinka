/** Prefijos telefónicos internacionales por país (código ISO → prefijo). Los nombres en español los
 * da el navegador (Intl.DisplayNames), así no hay que mantenerlos aquí. */
const DIAL_CODES = {
  AF: '+93', AL: '+355', DE: '+49', AD: '+376', AO: '+244', AG: '+1', SA: '+966', DZ: '+213', AR: '+54',
  AM: '+374', AW: '+297', AU: '+61', AT: '+43', AZ: '+994', BS: '+1', BD: '+880', BB: '+1', BH: '+973',
  BE: '+32', BZ: '+501', BJ: '+229', BY: '+375', BO: '+591', BA: '+387', BW: '+267', BR: '+55', BN: '+673',
  BG: '+359', BF: '+226', BI: '+257', BT: '+975', CV: '+238', KH: '+855', CM: '+237', CA: '+1', QA: '+974',
  TD: '+235', CL: '+56', CN: '+86', CY: '+357', CO: '+57', KM: '+269', CG: '+242', CD: '+243', KP: '+850',
  KR: '+82', CI: '+225', CR: '+506', HR: '+385', CU: '+53', CW: '+599', DK: '+45', DM: '+1', EC: '+593',
  EG: '+20', SV: '+503', AE: '+971', ER: '+291', SK: '+421', SI: '+386', ES: '+34', US: '+1', EE: '+372',
  SZ: '+268', ET: '+251', PH: '+63', FI: '+358', FJ: '+679', FR: '+33', GA: '+241', GM: '+220', GE: '+995',
  GH: '+233', GD: '+1', GR: '+30', GT: '+502', GN: '+224', GQ: '+240', GW: '+245', GY: '+592', HT: '+509',
  HN: '+504', HK: '+852', HU: '+36', IN: '+91', ID: '+62', IQ: '+964', IR: '+98', IE: '+353', IS: '+354',
  IL: '+972', IT: '+39', JM: '+1', JP: '+81', JO: '+962', KZ: '+7', KE: '+254', KG: '+996', KI: '+686',
  KW: '+965', LA: '+856', LS: '+266', LV: '+371', LB: '+961', LR: '+231', LY: '+218', LI: '+423', LT: '+370',
  LU: '+352', MO: '+853', MK: '+389', MG: '+261', MY: '+60', MW: '+265', MV: '+960', ML: '+223', MT: '+356',
  MA: '+212', MU: '+230', MR: '+222', MX: '+52', FM: '+691', MD: '+373', MC: '+377', MN: '+976', ME: '+382',
  MZ: '+258', MM: '+95', NA: '+264', NR: '+674', NP: '+977', NI: '+505', NE: '+227', NG: '+234', NO: '+47',
  NZ: '+64', OM: '+968', NL: '+31', PK: '+92', PW: '+680', PS: '+970', PA: '+507', PG: '+675', PY: '+595',
  PE: '+51', PL: '+48', PT: '+351', PR: '+1', GB: '+44', CF: '+236', CZ: '+420', DO: '+1', RW: '+250',
  RO: '+40', RU: '+7', WS: '+685', KN: '+1', SM: '+378', VC: '+1', LC: '+1', ST: '+239', SN: '+221',
  RS: '+381', SC: '+248', SL: '+232', SG: '+65', SY: '+963', SO: '+252', LK: '+94', ZA: '+27', SD: '+249',
  SS: '+211', SE: '+46', CH: '+41', SR: '+597', TH: '+66', TW: '+886', TZ: '+255', TJ: '+992', TL: '+670',
  TG: '+228', TO: '+676', TT: '+1', TN: '+216', TM: '+993', TR: '+90', TV: '+688', UA: '+380', UG: '+256',
  UY: '+598', UZ: '+998', VU: '+678', VE: '+58', VN: '+84', YE: '+967', DJ: '+253', ZM: '+260', ZW: '+263',
}

const names = (() => {
  try {
    return new Intl.DisplayNames(['es'], { type: 'region' })
  } catch {
    return null
  }
})()

export function countryName(iso) {
  return names?.of(iso) ?? iso
}

/** [{ iso, dial, name }] ordenados por nombre en español. */
export const COUNTRIES = Object.entries(DIAL_CODES)
  .map(([iso, dial]) => ({ iso, dial, name: countryName(iso) }))
  .sort((a, b) => a.name.localeCompare(b.name, 'es'))

export const DEFAULT_COUNTRY = 'CL'
