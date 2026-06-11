import FormField from './FormField';

/**
 * Grupo de cuatro campos de contacto: Nombre, Cargo, Teléfono, Correo.
 * Parametrizado por prefijo para reutilizarse en distintos contextos
 * (Órdenes de Compra, Reportes de Pago, etc.).
 */
export default function ContactGroup({
  titulo, prefijo, formData, onChange, onOpenHelp, errors, estiloTitulo,
}) {
  return (
    <>
      <h3 style={{ fontSize: '0.95rem', fontWeight: '600', color: 'var(--gray-800)', ...estiloTitulo }}>
        {titulo}
      </h3>
      <div className="form-row">
        <FormField
          label="Nombre" name={`${prefijo}_nombre`} required
          value={formData[`${prefijo}_nombre`]} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors[`${prefijo}_nombre`]}
        />
        <FormField
          label="Cargo" name={`${prefijo}_cargo`} required
          value={formData[`${prefijo}_cargo`]} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors[`${prefijo}_cargo`]}
        />
        <FormField
          label="Teléfono" name={`${prefijo}_telefono`} type="tel" required
          value={formData[`${prefijo}_telefono`]} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors[`${prefijo}_telefono`]}
        />
        <FormField
          label="Correo" name={`${prefijo}_correo`} type="email" required
          value={formData[`${prefijo}_correo`]} onChange={onChange}
          onOpenHelp={onOpenHelp} error={errors[`${prefijo}_correo`]}
        />
      </div>
    </>
  );
}
