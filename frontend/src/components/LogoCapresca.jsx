/**
 * Logotipo de la Caja de Crédito y Prestaciones de Catamarca, el mismo del portal de créditos.
 * Las letras son azul marino: en tema oscuro se usa la versión con letras claras (el verde se mantiene).
 */
export default function LogoCapresca({ className = "" }) {
  const alt = "Caja de Crédito y Prestaciones de Catamarca";
  return (
    <span className={className}>
      <img src="/logo-capresca.svg" alt={alt} className="h-full w-auto dark:hidden" />
      <img src="/logo-capresca-oscuro.svg" alt="" aria-hidden="true" className="h-full w-auto hidden dark:block" />
    </span>
  );
}
