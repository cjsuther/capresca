/**
 * Campo del código del doble factor: 6 dígitos de la app autenticadora o, si `recuperacion`, un código
 * de recuperación (XXXXX-XXXXX). El navegador lo puede autocompletar (autocomplete="one-time-code").
 */
export function CampoCodigo({ value, onChange, recuperacion = false, autoFocus = true, id = "codigo-2fa",
                              label }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-gray-700 mb-1">
        {label || (recuperacion ? "Código de recuperación" : "Código de 6 dígitos")}
      </label>
      <input
        id={id}
        type="text"
        inputMode={recuperacion ? "text" : "numeric"}
        autoComplete="one-time-code"
        maxLength={recuperacion ? 11 : 7}
        placeholder={recuperacion ? "XXXXX-XXXXX" : "123456"}
        className="input w-full text-center tracking-[0.3em] font-mono text-lg"
        value={value}
        onChange={(e) => onChange(recuperacion ? e.target.value.toUpperCase() : e.target.value.replace(/[^\d ]/g, ""))}
        autoFocus={autoFocus}
        required
      />
    </div>
  );
}

/** ¿El valor ya tiene la forma de un código para mandar? */
export function codigoCompleto(value, recuperacion = false) {
  const limpio = (value || "").replace(/[\s-]/g, "");
  return recuperacion ? /^[A-Za-z0-9]{10}$/.test(limpio) : /^\d{6}$/.test(limpio);
}
