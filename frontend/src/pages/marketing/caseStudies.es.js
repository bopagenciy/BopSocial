/* ============================================================================
 *  Bop Social — Marketing & Social Media Management Platform
 *  Spanish Localized Content for Case Studies (/customers/:slug)
 * ========================================================================== */

export const caseStudies_es = {
  // ── 1. Acme Realty ────────────────────────────────────────────────────────
  'acme-realty': {
    tagline: 'Cómo Acme multiplicó por 4.2 sus prospectos con WhatsApp y una bandeja unificada.',
    hero: {
      metric: { label: 'volumen de prospectos en 9 meses' },
      portrait: {
        role: 'Directora de Marketing, Acme Realty',
      },
    },
    profile: {
      sector: 'Bienes Raíces',
      size: '120 asesores · 6 ciudades',
      founded: '2014',
      location: 'Bombay · Pune · Bangalore',
      uses: ['WhatsApp Business', 'Bandeja unificada', 'Publicador', 'Informes'],
    },
    challenge: {
      title: 'El problema de "¿dónde respondo primero?"',
      body: [
        'Acme Realty operaba en tres plataformas fragmentadas (mensajes de Instagram, Messenger de Facebook y WhatsApp) con una única hoja de cálculo compartida en Google Sheets para registrar prospectos. Para 2024, recibían más de 12.000 consultas al mes. Los asesores tardaban más de 6 horas en ver los mensajes directos, los prospectos se enfriaban y la hoja de cálculo se convirtió en un cementerio de registros duplicados.',
        '"Teníamos dos pasantes a tiempo completo cuyo único trabajo era copiar manualmente números de WhatsApp en el CRM", explica Priya Sharma, directora de marketing. "Cada lunes por la mañana, el equipo perdía medio día conciliando listas y corrigiendo datos erróneos."',
      ],
    },
    solution: {
      title: 'Una sola bandeja. WhatsApp bidireccional. Enrutamiento automático.',
      body: [
        'Acme migró sus tres canales a la bandeja de entrada unificada de Bop Social. Los mensajes entrantes ahora se enrutan de forma automática al asesor de la ciudad correcta según el inmueble consultado. Las campañas de WhatsApp se enviaron mediante el Publicador con la voz de marca ajustada a un tono "cálido, ágil y profesional".',
        'El módulo de Informes proporciona a Priya una vista centralizada de "prospectos por fuente, por ciudad y por asesor", actualizada en vivo y enviada en un informe de marca blanca al director general cada lunes a primera hora.',
      ],
      bullets: [
        'Instagram, Facebook y WhatsApp en una sola bandeja de entrada y una única cola de atención.',
        'Reglas de enrutamiento automático por ciudad, tipología de inmueble y presupuesto.',
        'Campañas de difusión por WhatsApp segmentadas según la calificación del prospecto.',
        'Hilos de notas compartidas para que cualquier asesor pueda retomar la atención con contexto.',
      ],
    },
    results: {
      title: '4.2x prospectos. Tiempo de respuesta menor a 60 segundos.',
      body: 'En nueve meses utilizando Bop Social, Acme incrementó sus consultas mensuales de aproximadamente 12.000 a más de 50.000, sin contratar personal adicional para atención. El tiempo promedio de respuesta se mantiene por debajo de 60 segundos en todos los canales.',
      stats: [
        { label: 'volumen de prospectos' },
        { label: 'consultas mensuales' },
        { label: 'tiempo medio de respuesta' },
        { label: 'conversión a visitas' },
      ],
    },
    pulls: [
      {
        quote: 'Bop Social es la única herramienta que escaló con nosotros. Crecimos cuatro veces y nuestro equipo se hizo más ágil y eficiente.',
        person: 'Priya Sharma · Directora de Marketing',
      },
      {
        quote: 'El enrutamiento automático es extraordinario. Cada mensaje llega a la persona adecuada al primer intento.',
        person: 'Vikas Rao · Gerente de Ciudad, Pune',
      },
    ],
  },

  // ── 2. Sunrise Clinics ────────────────────────────────────────────────────
  'sunrise-clinics': {
    tagline: '12 clínicas. Una sola bandeja. 32% menos inasistencias a citas.',
    hero: {
      metric: { label: 'reducción de inasistencias médicas' },
      portrait: {
        role: 'Fundadora, Sunrise Clinics',
      },
    },
    profile: {
      sector: 'Salud · Red multisede',
      size: '12 clínicas · 80 colaboradores',
      founded: '2018',
      location: 'Bangalore · Mysore · Hubli',
      uses: ['WhatsApp Business', 'Automatizaciones', 'Bandeja unificada', 'Analítica'],
    },
    challenge: {
      title: 'Las ausencias consumían el 28% de los ingresos',
      body: [
        'Sunrise Clinics enfrentaba un problema silencioso pero muy costoso: el 28% de los pacientes reservaba cita y no se presentaba. Los recordatorios tradicionales por SMS eran ignorados, con tasas de lectura por debajo del 20%. La recepcionista de cada clínica realizaba llamadas manuales, pero con más de 200 citas diarias por sede, la mitad quedaba sin confirmar.',
        '"Estábamos perdiendo ingresos sustanciales cada mes debido a pacientes que no asistían", comenta la Dra. Anjali Verma. "Además, nuestro personal de recepción pasaba hasta 3 horas al día al teléfono en lugar de atender a quienes estaban en la sala de espera."',
      ],
    },
    solution: {
      title: 'Recordatorios por WhatsApp, automatizaciones y bandeja maestra',
      body: [
        'Sunrise integró su sistema de citas médicas con Bop Social mediante dos automatizaciones: un recordatorio por WhatsApp 24 horas antes y un aviso interactivo de confirmación o reprogramación 2 horas antes de la consulta. Los pacientes confirman con un solo toque o eligen un nuevo horario mediante un flujo guiado en el chat.',
        'Las 12 clínicas comparten una bandeja de entrada unificada. El equipo central de operaciones supervisa todas las conversaciones en tiempo real, mientras que la analítica mide el porcentaje de inasistencia por sede, médico y día de la semana.',
      ],
      bullets: [
        'Recordatorios a las 24h y 2h por WhatsApp con confirmación en un solo clic.',
        'Flujo interactivo de reprogramación directo en el chat sin llamadas.',
        'Bandeja maestra multisucursal para el equipo central de operaciones.',
        'Analítica de ausentismo por clínica, especialista y franja horaria.',
      ],
    },
    results: {
      title: 'Ausencias reducidas un 32%. Reservas duplicadas.',
      body: 'Tras tres meses de uso, la tasa de inasistencia cayó del 28% al 19% (una mejora relativa del 32%). Al liberar al personal de recepción de las llamadas rutinarias, Sunrise reasignó recursos a la atención de nuevos pacientes y duplicó las reservas totales.',
      stats: [
        { label: 'menos inasistencias' },
        { label: 'reservas totales' },
        { label: 'horas diarias ahorradas en recepción' },
        { label: 'tasa de lectura en WhatsApp' },
      ],
    },
    pulls: [
      {
        quote: 'Duplicamos las reservas sin contratar personal adicional. La rentabilidad es evidente.',
        person: 'Dra. Anjali Verma · Fundadora',
      },
      {
        quote: 'Los pacientes realmente responden por WhatsApp. Con los mensajes SMS tradicionales casi nadie interactuaba.',
        person: 'Anita Kumar · Gerente de Operaciones',
      },
    ],
  },

  // ── 3. BlueWave Agency ────────────────────────────────────────────────────
  'bluewave-agency': {
    tagline: 'Seis personas. Más de 120 clientes. Una sola instancia de Bop Social.',
    hero: {
      metric: { label: 'clientes gestionados en simultáneo' },
      portrait: {
        role: 'Fundador y CEO, BlueWave',
      },
    },
    profile: {
      sector: 'Agencia de Marketing Digital',
      size: '6 colaboradores · 120+ clientes',
      founded: '2021',
      location: 'Gurugram, India',
      uses: ['Multiinquilino', 'Portales de marca blanca', 'Publicador', 'Asistente de IA', 'Informes'],
    },
    challenge: {
      title: 'Herramientas que colapsaron al llegar a 30 clientes',
      body: [
        'BlueWave creció de 12 a 80 clientes en tan solo 18 meses. Su conjunto de herramientas (programadores dispersos, hojas de cálculo para reportes, Notion para aprobaciones y Slack para comunicación) comenzó a fallar. Las revisiones de contenido se perdían entre correos. Los informes mensuales exigían capturas de pantalla manuales en diapositivas cada viernes.',
        '"Al llegar al cliente número 30, pagábamos tarifas desmedidas en cuatro herramientas desconectadas", explica Rohit Mehta. "Y aún teníamos a tres personas dedicadas exclusivamente a unir datos y armar presentaciones."',
      ],
    },
    solution: {
      title: 'Un entorno aislado por cliente. Activos de marca integrados.',
      body: [
        'La arquitectura multiinquilino de Bop Social permitió que cada cliente de BlueWave tuviera su propio espacio de trabajo seguro bajo la cuenta principal de la agencia. Los portales de marca blanca muestran el logotipo del cliente y la identidad de la agencia. El Asistente de IA, entrenado con el historial de cada marca, redacta publicaciones con su tono exacto.',
        'Los informes se generan y envían de forma automática cada lunes. El Publicador permite programar semanas completas y las aprobaciones se realizan en la plataforma, sin cadenas de correos.',
      ],
      bullets: [
        'Aislamiento multiinquilino: cada cliente cuenta con su propio espacio seguro.',
        'Portales de marca blanca con la identidad corporativa de la agencia.',
        'Asistente de IA ajustado por cliente para preservar la coherencia de marca.',
        'Informes de marca blanca generados y entregados automáticamente cada lunes.',
      ],
    },
    results: {
      title: 'Más de 120 clientes. 70% de ahorro en software. Cero nómina adicional.',
      body: 'BlueWave multiplicó por 8 su cartera de clientes (de 12 a más de 120) sin necesidad de sumar personal operativo. Eliminaron tres herramientas heredadas, redujeron el gasto en suscripciones un 70% y transformaron ese ahorro en margen neto.',
      stats: [
        { label: 'clientes gestionados' },
        { label: 'ahorro en costos de software' },
        { label: 'velocidad de producción de contenido' },
        { label: 'herramientas reemplazadas' },
      ],
    },
    pulls: [
      {
        quote: 'Reemplazamos cuatro herramientas con Bop Social. Cuatro. El ahorro financió la operación de la agencia por un año.',
        person: 'Rohit Mehta · Fundador y CEO',
      },
      {
        quote: 'Los clientes nos preguntan cómo desarrollamos una plataforma tan completa. Es Bop Social con nuestros colores.',
        person: 'Karan Bhatia · Operaciones',
      },
    ],
  },
};
