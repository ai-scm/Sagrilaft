import FormField from '../FormField';
import LocationSelect from '../LocationSelect';
import AlertasInconsistencia from '../AlertasInconsistencia';
import { useUbicacion } from '../../hooks/useUbicacion';

const OPCIONES_TIPO_CONTRAPARTE = [
  { value: 'proveedor', label: 'Proveedor' },
  { value: 'cliente',   label: 'Cliente'   },
];

const OPCIONES_TIPO_PERSONA = [
  { value: 'juridica', label: 'Persona Jurídica' },
  { value: 'natural',  label: 'Persona Natural'  },
];

const OPCIONES_TIPO_SOLICITUD = [
  { value: 'vinculacion',   label: 'Vinculación'   },
  { value: 'actualizacion', label: 'Actualización' },
];

/**
 * Clasificación de la actividad comercial de la contraparte.
 * Fuente única de verdad — espeja los valores del enum ClasificacionActividad del backend.
 */
const OPCIONES_CLASIFICACION_ACTIVIDAD = [
  { value: 'C', label: 'Comercializador (C)'          },
  { value: 'D', label: 'Distribuidor autorizado (D)'  },
  { value: 'R', label: 'Representante (R)'            },
  { value: 'F', label: 'Fabricante (F)'               },
  { value: 'I', label: 'Importador (I)'               },
];

const OPCIONES_TIPO_IDENTIFICACION = [
  { value: 'NIT', label: 'NIT'                  },
  { value: 'CC',  label: 'Cédula de Ciudadanía' },
  { value: 'CE',  label: 'Cédula de Extranjería'},
  { value: 'PAS', label: 'Pasaporte'            },
];

const ESTILO_SEPARADOR_SECCION = {
  border: 'none',
  borderTop: '1px solid var(--gray-200)',
  margin: '24px 0',
};

function SeparadorSeccion() {
  return <hr style={ESTILO_SEPARADOR_SECCION} />;
}

function AlertasCampo({ alertas, tipoCampo, nombreCampo }) {
  return (
    <AlertasInconsistencia
      alertas={alertas}
      tipoCampo={tipoCampo}
      nombreCampo={nombreCampo}
    />
  );
}

/**
 * Paso 2 — Clasificación e Información Básica del Sujeto Obligado / Contraparte.
 */
export default function PasoInfoBasica(props) {
  const {
    formData,
    onChange,
    onOpenHelp,
    errors,
    alertasRazonSocial,
    alertasNit,
    alertasDireccion,
  } = props;

  const {
    paisesOptions, departamentosOptions, ciudadesOptions,
    selectedPais, selectedDepartamento, selectedCiudad,
    handlePaisChange, handleDepartamentoChange, handleCiudadChange,
  } = useUbicacion(formData, onChange);

  const renderCampo = ({ label, name, type, required, options }) => (
    <FormField
      key={name}
      label={label}
      name={name}
      type={type}
      required={required}
      value={formData[name]}
      onChange={onChange}
      onOpenHelp={onOpenHelp}
      error={errors[name]}
      options={options}
    />
  );

  return (
    <div className="form-card">
      <h2 className="section-title">CLASIFICACION E INFORMACIÓN BASICA DE LA EMPRESA</h2>
      <p className="section-subtitle">Datos generales de la empresa</p>

      <div className="form-row">
        {[
          {
            label: 'Tipo de Contraparte',
            name: 'tipo_contraparte',
            type: 'select',
            required: true,
            options: OPCIONES_TIPO_CONTRAPARTE,
          },
          {
            label: 'Tipo de Persona',
            name: 'tipo_persona',
            type: 'select',
            required: true,
            options: OPCIONES_TIPO_PERSONA,
          },
          {
            label: 'Tipo de Solicitud',
            name: 'tipo_solicitud',
            type: 'select',
            required: true,
            options: OPCIONES_TIPO_SOLICITUD,
          },
          {
            label: 'Clasificación de Actividad',
            name: 'clasificacion_actividad',
            type: 'select',
            required: true,
            options: OPCIONES_CLASIFICACION_ACTIVIDAD,
          },
        ].map(renderCampo)}
      </div>

      <SeparadorSeccion />

      <div className="form-row single">
        {renderCampo({
          label: 'Nombre o Razón Social',
          name: 'razon_social',
          required: true,
        })}
      </div>

      <AlertasCampo
        alertas={alertasRazonSocial}
        tipoCampo="nombre sin resolver"
        nombreCampo="Nombre o Razón Social"
      />

      <div className="form-row">
        {[
          {
            label: 'Tipo de Identificación',
            name: 'tipo_identificacion',
            type: 'select',
            required: true,
            options: OPCIONES_TIPO_IDENTIFICACION,
          },
          {
            label: 'Número de Identificación',
            name: 'numero_identificacion',
            required: true,
          },
          {
            label: 'DV',
            name: 'digito_verificacion',
            required: true,
          },
        ].map(renderCampo)}
      </div>

      <AlertasCampo
        alertas={alertasNit}
        tipoCampo="NIT sin resolver"
        nombreCampo="Número de Identificación"
      />

      <div className="form-row single">
        {renderCampo({
          label: 'Dirección',
          name: 'direccion',
          required: true,
        })}
      </div>

      <AlertasCampo
        alertas={alertasDireccion}
        tipoCampo="dirección sin resolver"
        nombreCampo="Dirección"
      />

      <div className="form-row">
        <LocationSelect
          label="País" name="pais"
          value={selectedPais} onChange={handlePaisChange}
          options={paisesOptions}
          onOpenHelp={onOpenHelp} error={errors.pais}
        />
        <LocationSelect
          label="Departamento" name="departamento" required
          value={selectedDepartamento} onChange={handleDepartamentoChange}
          options={departamentosOptions}
          disabled={!formData.pais}
          onOpenHelp={onOpenHelp} error={errors.departamento}
        />
        <LocationSelect
          label="Ciudad" name="ciudad" required
          value={selectedCiudad} onChange={handleCiudadChange}
          options={ciudadesOptions}
          disabled={!formData.departamento}
          onOpenHelp={onOpenHelp} error={errors.ciudad}
        />
      </div>

      <div className="form-row">
        {[
          {
            label: 'Teléfono',
            name: 'telefono',
            type: 'tel',
            required: true,
          },
          {
            label: 'Fax',
            name: 'fax',
            required: true,
          },
          {
            label: 'Correo Electrónico',
            name: 'correo',
            type: 'email',
            required: true,
          },
        ].map(renderCampo)}
      </div>

      <div className="form-row">
        {[
          {
            label: 'Código Actividad ICA',
            name: 'codigo_ica',
            required: true,
          },
          {
            label: 'Página Web',
            name: 'pagina_web',
            required: true,
          },
        ].map(renderCampo)}
      </div>
    </div>
  );
}
