import { useEffect, useMemo, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  Calculator,
  Database,
  FileSpreadsheet,
  RefreshCcw,
  RotateCcw,
  Save,
  Upload,
} from 'lucide-react';

const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: options.body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || 'Error desconocido');
  }
  return response.json();
};

const fmt = (value, digits = 0) =>
  new Intl.NumberFormat('es-PE', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(Number.isFinite(Number(value)) ? Number(value) : 0);

const pct = (value, digits = 1) => `${fmt((Number(value) || 0) * 100, digits)}%`;

const tabs = [
  { id: 'calculator', label: 'Calculadora WFM', icon: Calculator },
  { id: 'case', label: 'Caso de estudio', icon: Database },
  { id: 'imports', label: 'Cargar registros', icon: Upload },
];

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function Card({ title, value, sub }) {
  return (
    <div className="card kpi-card">
      <span className="muted">{title}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}

function Section({ title, subtitle, children, right }) {
  return (
    <section className="card section-card">
      <div className="section-head">
        <div>
          <div className="section-title">{title}</div>
          {subtitle && <p className="muted no-margin">{subtitle}</p>}
        </div>
        {right}
      </div>
      {children}
    </section>
  );
}

function NumberInput({ label, value, onChange, step = 'any', min, suffix, hint }) {
  return (
    <label className="field">
      <span>{label}</span>
      <div className="input-row">
        <input
          type="number"
          step={step}
          min={min}
          value={value ?? ''}
          onChange={(event) => onChange(event.target.value === '' ? 0 : Number(event.target.value))}
        />
        {suffix && <b>{suffix}</b>}
      </div>
      {hint && <small>{hint}</small>}
    </label>
  );
}

function TextInput({ label, value, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input value={value ?? ''} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function Formula({ children }) {
  return <code className="formula">{children}</code>;
}

function ResultTable({ rows }) {
  return (
    <div className="table-wrap compact">
      <table>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th>{row.label}</th>
              <td>{row.value}</td>
              {row.formula && <td className="formula-cell"><Formula>{row.formula}</Formula></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExerciseOne({ payload, result, updateExercise }) {
  return (
    <Section
      title="Ejercicio 1: calcular AHT inbound"
      subtitle="Replica la hoja 1.-Cálculo: convierte horas programadas en horas transaccionales y calcula AHT."
    >
      <div className="grid two-columns align-start">
        <div className="form-grid">
          <NumberInput label="Horas programadas (Scheduled)" value={payload.scheduled_hours} onChange={(v) => updateExercise('exercise1', 'scheduled_hours', v)} />
          <NumberInput label="Ausentismo" value={payload.absenteeism} onChange={(v) => updateExercise('exercise1', 'absenteeism', v)} hint={`Actual: ${pct(payload.absenteeism, 2)}`} />
          <NumberInput label="Auxiliares" value={payload.auxiliaries} onChange={(v) => updateExercise('exercise1', 'auxiliaries', v)} hint={`Actual: ${pct(payload.auxiliaries, 2)}`} />
          <NumberInput label="Inbound Availtime" value={payload.inbound_availtime} onChange={(v) => updateExercise('exercise1', 'inbound_availtime', v)} hint={`Actual: ${pct(payload.inbound_availtime, 2)}`} />
          <NumberInput label="NDA" value={payload.nda} onChange={(v) => updateExercise('exercise1', 'nda', v)} hint={`Actual: ${pct(payload.nda, 2)}`} />
          <NumberInput label="NDS" value={payload.nds} onChange={(v) => updateExercise('exercise1', 'nds', v)} hint="Premisa del examen; no afecta este cálculo directo." />
          <NumberInput label="Llamadas" value={payload.calls} onChange={(v) => updateExercise('exercise1', 'calls', v)} />
        </div>
        <div className="result-panel highlight">
          <span>Resultado principal</span>
          <strong>{fmt(result?.inbound_aht_sec, 3)} seg</strong>
          <small>AHT inbound</small>
          <Formula>AHT = (Horas transaccionales × 3600) / llamadas atendidas</Formula>
        </div>
      </div>
      {result && (
        <ResultTable rows={[
          { label: 'Attendance hours', value: fmt(result.attendance_hours, 3), formula: 'Scheduled × (1 - Ausentismo)' },
          { label: 'Productive hours', value: fmt(result.productive_hours, 3), formula: 'Attendance × (1 - Auxiliares)' },
          { label: 'Ocupación', value: pct(result.occupancy, 2), formula: '1 - Inbound Availtime' },
          { label: 'Transactional hours', value: fmt(result.transactional_hours, 3), formula: 'Productive × Ocupación' },
          { label: 'Answered calls', value: fmt(result.answered_calls, 0), formula: 'Llamadas × NDA' },
        ]} />
      )}
    </Section>
  );
}

function ExerciseTwo({ payload, result, updateExercise }) {
  return (
    <Section
      title="Ejercicio 2: calcular horas presentes y horas programadas"
      subtitle="Replica el segundo bloque de la hoja 1.-Cálculo."
    >
      <div className="grid two-columns align-start">
        <div className="form-grid">
          <NumberInput label="Inbound AHT (seg)" value={payload.inbound_aht_sec} onChange={(v) => updateExercise('exercise2', 'inbound_aht_sec', v)} />
          <NumberInput label="Llamadas" value={payload.calls} onChange={(v) => updateExercise('exercise2', 'calls', v)} />
          <NumberInput label="NDA" value={payload.nda} onChange={(v) => updateExercise('exercise2', 'nda', v)} hint={`Actual: ${pct(payload.nda, 2)}`} />
          <NumberInput label="Ocupación inbound" value={payload.inbound_occupancy} onChange={(v) => updateExercise('exercise2', 'inbound_occupancy', v)} hint={`Actual: ${pct(payload.inbound_occupancy, 2)}`} />
          <NumberInput label="Hrs productivas Back Office" value={payload.productive_hours_backoffice} onChange={(v) => updateExercise('exercise2', 'productive_hours_backoffice', v)} />
          <NumberInput label="Hrs productivas Email" value={payload.productive_hours_email} onChange={(v) => updateExercise('exercise2', 'productive_hours_email', v)} />
          <NumberInput label="Vacaciones" value={payload.vacations} onChange={(v) => updateExercise('exercise2', 'vacations', v)} hint={`Actual: ${pct(payload.vacations, 2)}`} />
          <NumberInput label="Auxiliares (hr)" value={payload.auxiliary_hours} onChange={(v) => updateExercise('exercise2', 'auxiliary_hours', v)} />
        </div>
        <div className="result-stack">
          <div className="result-panel highlight">
            <span>Horas presentes</span>
            <strong>{fmt(result?.attended_hours, 3)}</strong>
            <small>Equivale a G23/G18 en el Excel</small>
          </div>
          <div className="result-panel">
            <span>Horas programadas</span>
            <strong>{fmt(result?.scheduled_hours, 3)}</strong>
            <small>Incluye vacaciones</small>
          </div>
        </div>
      </div>
      {result && (
        <ResultTable rows={[
          { label: 'Answered calls', value: fmt(result.answered_calls, 0), formula: 'Llamadas × NDA' },
          { label: 'Inbound transactional hours', value: fmt(result.inbound_transactional_hours, 3), formula: '(Answered × AHT) / 3600' },
          { label: 'Inbound productive hours', value: fmt(result.inbound_productive_hours, 3), formula: 'Transactional / Ocupación' },
          { label: 'Total productive hours', value: fmt(result.total_productive_hours, 3), formula: 'Inbound + Back Office + Email' },
          { label: 'Attended hours', value: fmt(result.attended_hours, 3), formula: 'Productive total + Auxiliares hr' },
          { label: 'Scheduled hours', value: fmt(result.scheduled_hours, 3), formula: 'Attended / (1 - Vacaciones)' },
        ]} />
      )}
    </Section>
  );
}

function ExerciseThree({ payload, result, updateShift }) {
  return (
    <Section
      title="Ejercicio 3: AHT por turno y AHT global"
      subtitle="Todos los turnos del examen vienen cargados por defecto y se pueden editar."
    >
      <div className="table-wrap editable-table">
        <table>
          <thead>
            <tr>
              <th>Turno</th>
              <th>Llamadas atendidas</th>
              <th>Conversación min</th>
              <th>ACW min</th>
              <th>Agentes</th>
              <th>Horas logadas</th>
              <th>AHT seg</th>
            </tr>
          </thead>
          <tbody>
            {payload.shifts.map((shift, index) => (
              <tr key={`${shift.shift}-${index}`}>
                <td><input value={shift.shift} onChange={(e) => updateShift(index, 'shift', e.target.value)} /></td>
                <td><input type="number" value={shift.answered_calls} onChange={(e) => updateShift(index, 'answered_calls', Number(e.target.value))} /></td>
                <td><input type="number" step="any" value={shift.talk_minutes} onChange={(e) => updateShift(index, 'talk_minutes', Number(e.target.value))} /></td>
                <td><input type="number" step="any" value={shift.acw_minutes} onChange={(e) => updateShift(index, 'acw_minutes', Number(e.target.value))} /></td>
                <td><input type="number" value={shift.agents} onChange={(e) => updateShift(index, 'agents', Number(e.target.value))} /></td>
                <td><input type="number" value={shift.logged_hours} onChange={(e) => updateShift(index, 'logged_hours', Number(e.target.value))} /></td>
                <td><b>{fmt(result?.shifts?.[index]?.aht_sec, 3)}</b></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid two-columns align-start top-space">
        <div className="result-panel highlight">
          <span>AHT global</span>
          <strong>{fmt(result?.global_aht_sec, 3)} seg</strong>
          <Formula>AHT global = SUM(Conversación + ACW) / SUM(Atendidas) × 60</Formula>
        </div>
        <div className="note-box">
          <b>Acciones sugeridas del examen</b>
          <ul>
            {payload.recommendations?.map((item, index) => <li key={index}>{item}</li>)}
          </ul>
        </div>
      </div>
    </Section>
  );
}

function Dimensioning({ payload, result, setDimensioning }) {
  const update = (key, value) => setDimensioning((current) => ({ ...current, [key]: value }));
  const updateDay = (index, key, value) => {
    setDimensioning((current) => {
      const days = current.days.map((day, idx) => (idx === index ? { ...day, [key]: value } : day));
      return { ...current, days };
    });
  };

  return (
    <Section
      title="Dimensionado: agentes requeridos, HC + shrinkage y mix FT/PT"
      subtitle="Replica la hoja 2.- Dimensionado con inputs editables y resultados automáticos."
    >
      <div className="grid three-columns align-start">
        <div className="form-grid dense">
          <NumberInput label="Llamadas semana total" value={payload.weekly_calls} onChange={(v) => update('weekly_calls', v)} />
          <NumberInput label="AHT (seg)" value={payload.aht_sec} onChange={(v) => update('aht_sec', v)} />
          <NumberInput label="Ausentismo / vacaciones" value={payload.absenteeism} onChange={(v) => update('absenteeism', v)} hint={`Actual: ${pct(payload.absenteeism, 2)}`} />
          <NumberInput label="Auxiliares" value={payload.auxiliaries} onChange={(v) => update('auxiliaries', v)} hint={`Actual: ${pct(payload.auxiliaries, 2)}`} />
        </div>
        <div className="form-grid dense">
          <NumberInput label="Ocupación objetivo" value={payload.occupancy_target} onChange={(v) => update('occupancy_target', v)} hint={`Actual: ${pct(payload.occupancy_target, 2)}`} />
          <NumberInput label="SLA tiempo (seg)" value={payload.sla_time_sec} onChange={(v) => update('sla_time_sec', v)} />
          <NumberInput label="SLA nivel" value={payload.sla_level} onChange={(v) => update('sla_level', v)} hint={`Actual: ${pct(payload.sla_level, 2)}`} />
          <NumberInput label="% Part-Time a contratar" value={payload.part_time_ratio} onChange={(v) => update('part_time_ratio', v)} hint={`Actual: ${pct(payload.part_time_ratio, 2)}`} />
        </div>
        <div className="form-grid dense">
          <NumberInput label="Horas FT semana" value={payload.ft_hours_week} onChange={(v) => update('ft_hours_week', v)} />
          <NumberInput label="Horas PT semana" value={payload.pt_hours_week} onChange={(v) => update('pt_hours_week', v)} />
          <div className="result-panel">
            <span>Shrinkage</span>
            <strong>{fmt(result?.assumptions?.shrinkage, 4)}</strong>
            <small>1 / ((1 - ausentismo) × (1 - auxiliares))</small>
          </div>
        </div>
      </div>

      <div className="section-subtitle">Distribución de tráfico por día</div>
      <div className="table-wrap editable-table">
        <table>
          <thead>
            <tr>
              <th>Día</th>
              <th>% Tráfico</th>
              <th>Horas operativas</th>
              <th>Llamadas por día</th>
              <th>Calls/hora</th>
              <th>Tráfico Erlang</th>
              <th>Agentes pos.</th>
              <th>HC + shrinkage</th>
              <th>FTE por día</th>
              <th>Erlang C ref.</th>
            </tr>
          </thead>
          <tbody>
            {payload.days.map((day, index) => {
              const row = result?.rows?.[index] || {};
              return (
                <tr key={`${day.day}-${index}`}>
                  <td><input value={day.day} onChange={(e) => updateDay(index, 'day', e.target.value)} /></td>
                  <td><input type="number" step="any" value={day.traffic_pct} onChange={(e) => updateDay(index, 'traffic_pct', Number(e.target.value))} /></td>
                  <td><input type="number" step="any" value={day.operating_hours} onChange={(e) => updateDay(index, 'operating_hours', Number(e.target.value))} /></td>
                  <td>{fmt(row.calls_day, 2)}</td>
                  <td>{fmt(row.calls_hour, 2)}</td>
                  <td>{fmt(row.traffic_erlang, 2)}</td>
                  <td><b>{fmt(row.agents_position, 0)}</b></td>
                  <td><b>{fmt(row.hc_shrinkage, 0)}</b></td>
                  <td>{fmt(row.fte_day, 2)}</td>
                  <td>{fmt(row.agents_erlang_c, 0)}</td>
                </tr>
              );
            })}
            {result?.totals && (
              <tr className="total-row">
                <td>Total</td>
                <td>{pct(result.totals.traffic_pct, 2)}</td>
                <td>—</td>
                <td>{fmt(result.totals.calls_day, 0)}</td>
                <td>{fmt(result.totals.calls_hour, 2)}</td>
                <td>{fmt(result.totals.traffic_erlang, 2)}</td>
                <td>{fmt(result.totals.agents_position, 0)}</td>
                <td>{fmt(result.totals.hc_shrinkage, 0)}</td>
                <td>{fmt(result.totals.fte_day, 2)}</td>
                <td>—</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {result && (
        <div className="grid two-columns align-start top-space">
          <div className="card inner-card">
            <div className="section-title">Resumen contractual</div>
            <div className="table-wrap compact">
              <table>
                <thead><tr><th>Concepto</th><th>Solo FT</th><th>FT + PT</th><th>Diferencia</th></tr></thead>
                <tbody>
                  <tr><td>HC pico requerido</td><td>{fmt(result.contract_model.solo_ft.hc_peak_required)}</td><td>{fmt(result.contract_model.ft_pt_mix.hc_peak_required)}</td><td>0</td></tr>
                  <tr><td>% Part-Time elegido</td><td>{pct(result.contract_model.solo_ft.part_time_ratio)}</td><td>{pct(result.contract_model.ft_pt_mix.part_time_ratio)}</td><td>n/a</td></tr>
                  <tr><td>Personas FT</td><td>{fmt(result.contract_model.solo_ft.ft_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.ft_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.ft_people - result.contract_model.solo_ft.ft_people)}</td></tr>
                  <tr><td>Personas PT</td><td>{fmt(result.contract_model.solo_ft.pt_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.pt_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.pt_people - result.contract_model.solo_ft.pt_people)}</td></tr>
                  <tr><td>Total personas HC</td><td>{fmt(result.contract_model.solo_ft.total_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.total_people)}</td><td>{fmt(result.contract_model.ft_pt_mix.total_people - result.contract_model.solo_ft.total_people)}</td></tr>
                  <tr><td>FTE total a contratar</td><td>{fmt(result.contract_model.solo_ft.fte_total, 2)}</td><td>{fmt(result.contract_model.ft_pt_mix.fte_total, 2)}</td><td>{fmt(result.contract_model.ft_pt_mix.fte_total - result.contract_model.solo_ft.fte_total, 2)}</td></tr>
                  <tr><td>Ahorro FTE</td><td>—</td><td>{pct(result.contract_model.fte_saving_pct, 2)}</td><td>{fmt(result.contract_model.fte_saving, 2)}</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div className="card inner-card">
            <div className="section-title">Fórmulas principales</div>
            <p><Formula>Llamadas día = llamadas semana × % tráfico</Formula></p>
            <p><Formula>Tráfico Erlang = calls/hora × AHT / 3600</Formula></p>
            <p><Formula>Agentes posición = ROUNDUP(Erlang / ocupación)</Formula></p>
            <p><Formula>HC + shrinkage = ROUNDUP(Agentes × shrinkage)</Formula></p>
            <p className="muted">La columna Erlang C es una referencia adicional para SLA 80/20; el cálculo principal replica la lógica simple del Excel.</p>
          </div>
        </div>
      )}
    </Section>
  );
}

function CalculatorPage({ exercisesScenario, dimensioningScenario, setExercisesScenario, setDimensioningScenario, exerciseResult, dimensioningResult, saveAll, resetDefaults, status }) {
  if (!exercisesScenario?.payload || !dimensioningScenario?.payload) {
    return <div className="card">Cargando calculadora con los valores del examen...</div>;
  }

  const exercises = exercisesScenario.payload;
  const dimensioning = dimensioningScenario.payload;

  const updateExercise = (section, key, value) => {
    setExercisesScenario((current) => ({
      ...current,
      payload: {
        ...current.payload,
        [section]: {
          ...current.payload[section],
          [key]: value,
        },
      },
    }));
  };

  const updateShift = (index, key, value) => {
    setExercisesScenario((current) => ({
      ...current,
      payload: {
        ...current.payload,
        exercise3: {
          ...current.payload.exercise3,
          shifts: current.payload.exercise3.shifts.map((shift, idx) => (idx === index ? { ...shift, [key]: value } : shift)),
        },
      },
    }));
  };

  return (
    <div className="stack">
      <div className="hero card">
        <div>
          <span className="eyebrow">Web calculator basada en el Excel</span>
          <h2>Calculadora WFM del Examen de Planeamiento</h2>
          <p>
            Todos los campos del examen están cargados como ejemplo. Puedes cambiar cualquier valor y la web recalcula AHT, horas requeridas,
            dimensionado, HC + shrinkage y mix FT/PT.
          </p>
        </div>
        <div className="actions hero-actions">
          <button onClick={saveAll}><Save size={16} /> Guardar escenario</button>
          <button className="secondary" onClick={resetDefaults}><RotateCcw size={16} /> Restaurar examen</button>
        </div>
      </div>

      {status && <div className="success">{status}</div>}

      <div className="grid kpi-grid">
        <Card title="AHT inbound" value={`${fmt(exerciseResult?.exercise1?.inbound_aht_sec, 3)} seg`} sub="Ejercicio 1" />
        <Card title="Horas presentes" value={fmt(exerciseResult?.exercise2?.attended_hours, 3)} sub="Ejercicio 2" />
        <Card title="Horas programadas" value={fmt(exerciseResult?.exercise2?.scheduled_hours, 3)} sub="Ejercicio 2" />
        <Card title="AHT global turnos" value={`${fmt(exerciseResult?.exercise3?.global_aht_sec, 3)} seg`} sub="Ejercicio 3" />
        <Card title="HC pico + shrinkage" value={fmt(dimensioningResult?.contract_model?.solo_ft?.hc_peak_required, 0)} sub="Dimensionado" />
        <Card title="Ahorro FTE con PT" value={pct(dimensioningResult?.contract_model?.fte_saving_pct, 2)} sub="Mix FT/PT" />
      </div>

      <ExerciseOne payload={exercises.exercise1} result={exerciseResult?.exercise1} updateExercise={updateExercise} />
      <ExerciseTwo payload={exercises.exercise2} result={exerciseResult?.exercise2} updateExercise={updateExercise} />
      <ExerciseThree payload={exercises.exercise3} result={exerciseResult?.exercise3} updateShift={updateShift} />
      <Dimensioning payload={dimensioning} result={dimensioningResult} setDimensioning={(next) => setDimensioningScenario((current) => ({ ...current, payload: typeof next === 'function' ? next(current.payload) : next }))} />
    </div>
  );
}

function CaseStudyPage({ analytics }) {
  if (!analytics) return <div className="card">Cargando indicadores del caso de estudio...</div>;

  const { global, insights } = analytics;
  return (
    <div className="stack">
      <div className="hero card">
        <div>
          <span className="eyebrow">Hoja 3. Caso de Estudio</span>
          <h2>Análisis del histórico de llamadas</h2>
          <p>Este módulo usa los registros del examen por defecto y acepta nuevos registros con la misma estructura.</p>
        </div>
      </div>

      <div className="grid kpi-grid">
        <Card title="Llamadas recibidas" value={fmt(global.recibidas)} sub={`${fmt(analytics.total_rows)} intervalos`} />
        <Card title="Llamadas atendidas" value={fmt(global.atendidas)} sub={`Answer Rate ${pct(global.answer_rate, 2)}`} />
        <Card title="Abandonadas" value={fmt(global.abandonadas)} sub={`Abandono ${pct(global.abandon_rate, 2)}`} />
        <Card title="Atendidas SLA" value={fmt(global.atendidas_sla)} sub={`SLA ${pct(global.sla, 2)}`} />
        <Card title="AHT ponderado" value={`${fmt(global.aht_pond, 2)} seg`} />
        <Card title="ASA / TME" value={`${fmt(global.asa, 2)} seg`} />
      </div>

      <div className="grid two-columns">
        <div className="card chart-card">
          <div className="section-title">SLA y abandono por mes</div>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={analytics.by_month}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" />
              <YAxis tickFormatter={(v) => `${Math.round(v * 100)}%`} />
              <Tooltip formatter={(value) => pct(value, 2)} />
              <Legend />
              <Line type="monotone" dataKey="sla" name="SLA" strokeWidth={2} />
              <Line type="monotone" dataKey="abandon_rate" name="Abandono" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="card chart-card">
          <div className="section-title">Recibidas por hora</div>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={analytics.by_hour}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" interval={1} />
              <YAxis />
              <Tooltip formatter={(value) => fmt(value)} />
              <Bar dataKey="recibidas" name="Recibidas" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid three-columns align-start">
        <div className="card">
          <div className="section-title">Lectura automática</div>
          <p>Mes más crítico por SLA: <b>{insights.critical_month?.label}</b> con <b>{pct(insights.critical_month?.sla)}</b>.</p>
          <p>Día más crítico: <b>{insights.critical_day?.label}</b> con <b>{pct(insights.critical_day?.sla)}</b>.</p>
          <p>Hora pico por volumen: <b>{insights.peak_hour?.label}</b> con <b>{fmt(insights.peak_hour?.recibidas)}</b> recibidas.</p>
        </div>
        <TableCard title="Por día" rows={analytics.by_day} columns={[
          ['label', 'Día'],
          ['recibidas', 'Recibidas', fmt],
          ['abandon_rate', 'Abandono', pct],
          ['sla', 'SLA', pct],
        ]} />
        <TableCard title="Por semana" rows={analytics.by_week.slice(0, 10)} columns={[
          ['label', 'Semana'],
          ['recibidas', 'Recibidas', fmt],
          ['sla', 'SLA', pct],
        ]} />
      </div>
    </div>
  );
}

function TableCard({ title, rows, columns }) {
  return (
    <div className="card table-card">
      <div className="section-title">{title}</div>
      <div className="table-wrap compact">
        <table>
          <thead>
            <tr>{columns.map((column) => <th key={column[0]}>{column[1]}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={`${row.label || row.id || index}-${index}`}>
                {columns.map(([key, , format]) => <td key={key}>{format ? format(row[key]) : row[key]}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ImportPage({ records, reloadAll, resetDefaults }) {
  const [mode, setMode] = useState('replace');
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');
  const [manual, setManual] = useState({
    fecha: 20260519,
    semana: 'Sem21',
    hora: 8,
    recibidas: 100,
    atendidas: 90,
    abandonada: 10,
    atendidas_sla: 70,
    aht_seg: 180,
    tme_seg: 30,
  });

  const uploadFile = async () => {
    if (!file) {
      setMessage('Selecciona un CSV o XLSX primero.');
      return;
    }
    const form = new FormData();
    form.append('file', file);
    const result = await api(`/api/records/upload?mode=${mode}`, { method: 'POST', body: form });
    setMessage(`Archivo cargado: ${fmt(result.inserted)} registros (${result.mode}).`);
    await reloadAll();
  };

  const createManual = async (event) => {
    event.preventDefault();
    await api('/api/records', { method: 'POST', body: JSON.stringify(manual) });
    setMessage('Registro manual agregado.');
    await reloadAll();
  };

  return (
    <div className="stack">
      <div className="hero card">
        <div>
          <span className="eyebrow">Datos editables</span>
          <h2>Cargar registros del caso de estudio</h2>
          <p>Acepta CSV o XLSX con columnas: mes, fecha, semana, hora, Recibidas, Atendidas, abandonada, Atendidas dentro de SLA, AHT_Seg y TME_Seg.</p>
        </div>
      </div>

      {message && <div className="success">{message}</div>}

      <div className="grid two-columns align-start">
        <Section title="Importar archivo" subtitle="Puedes reemplazar el ejemplo o agregar datos encima.">
          <div className="upload-box">
            <Upload size={26} />
            <input type="file" accept=".csv,.xlsx,.xlsm" onChange={(event) => setFile(event.target.files?.[0] || null)} />
          </div>
          <label className="field">
            <span>Modo de carga</span>
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="replace">Reemplazar registros actuales</option>
              <option value="append">Agregar a los registros actuales</option>
            </select>
          </label>
          <div className="actions">
            <button onClick={uploadFile}><Upload size={16} /> Cargar archivo</button>
            <button className="secondary" onClick={resetDefaults}><RotateCcw size={16} /> Restaurar ejemplo completo</button>
          </div>
        </Section>

        <Section title="Agregar un registro manual" subtitle="Útil para probar valores aislados.">
          <form className="form-grid" onSubmit={createManual}>
            <NumberInput label="Fecha YYYYMMDD" value={manual.fecha} onChange={(v) => setManual({ ...manual, fecha: v })} />
            <TextInput label="Semana" value={manual.semana} onChange={(v) => setManual({ ...manual, semana: v })} />
            <NumberInput label="Hora" value={manual.hora} onChange={(v) => setManual({ ...manual, hora: v })} min={0} />
            <NumberInput label="Recibidas" value={manual.recibidas} onChange={(v) => setManual({ ...manual, recibidas: v })} min={0} />
            <NumberInput label="Atendidas" value={manual.atendidas} onChange={(v) => setManual({ ...manual, atendidas: v })} min={0} />
            <NumberInput label="Abandonadas" value={manual.abandonada} onChange={(v) => setManual({ ...manual, abandonada: v })} min={0} />
            <NumberInput label="Atendidas dentro SLA" value={manual.atendidas_sla} onChange={(v) => setManual({ ...manual, atendidas_sla: v })} min={0} />
            <NumberInput label="AHT seg" value={manual.aht_seg} onChange={(v) => setManual({ ...manual, aht_seg: v })} min={0} />
            <NumberInput label="TME seg" value={manual.tme_seg} onChange={(v) => setManual({ ...manual, tme_seg: v })} min={0} />
            <button type="submit">Agregar registro</button>
          </form>
        </Section>
      </div>

      <Section title="Últimos registros cargados" subtitle={`${fmt(records?.total)} registros actuales en SQLite`}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Fecha</th><th>Semana</th><th>Hora</th><th>Recibidas</th><th>Atendidas</th><th>Aband.</th><th>SLA</th><th>AHT</th><th>TME</th></tr>
            </thead>
            <tbody>
              {records?.items?.slice(0, 100).map((row) => (
                <tr key={row.id}>
                  <td>{row.fecha}</td><td>{row.semana}</td><td>{row.hora}</td><td>{fmt(row.recibidas)}</td><td>{fmt(row.atendidas)}</td><td>{fmt(row.abandonada)}</td><td>{fmt(row.atendidas_sla)}</td><td>{fmt(row.aht_seg, 2)}</td><td>{fmt(row.tme_seg, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

export default function App() {
  const [active, setActive] = useState('calculator');
  const [analytics, setAnalytics] = useState(null);
  const [records, setRecords] = useState(null);
  const [dimensioningScenario, setDimensioningScenario] = useState(null);
  const [exercisesScenario, setExercisesScenario] = useState(null);
  const [exerciseResult, setExerciseResult] = useState(null);
  const [dimensioningResult, setDimensioningResult] = useState(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');

  const reloadAll = async () => {
    try {
      setError('');
      const [analyticsData, recordsData, dimData, exercisesData] = await Promise.all([
        api('/api/analytics'),
        api('/api/records?limit=100'),
        api('/api/scenarios/dimensioning'),
        api('/api/scenarios/exercises'),
      ]);
      setAnalytics(analyticsData);
      setRecords(recordsData);
      setDimensioningScenario(dimData);
      setExercisesScenario(exercisesData);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    reloadAll();
  }, []);

  useEffect(() => {
    if (!exercisesScenario?.payload) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const data = await api('/api/calculators/exercises', { method: 'POST', body: JSON.stringify(exercisesScenario.payload) });
        if (!cancelled) setExerciseResult(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [exercisesScenario]);

  useEffect(() => {
    if (!dimensioningScenario?.payload) return undefined;
    let cancelled = false;
    const timer = setTimeout(async () => {
      try {
        const data = await api('/api/calculators/dimensioning', { method: 'POST', body: JSON.stringify(dimensioningScenario.payload) });
        if (!cancelled) setDimensioningResult(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      }
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [dimensioningScenario]);

  const saveAll = async () => {
    try {
      setError('');
      await Promise.all([
        api('/api/scenarios/exercises', {
          method: 'PUT',
          body: JSON.stringify({ name: exercisesScenario.name || 'Ejercicios WFM', payload: exercisesScenario.payload }),
        }),
        api('/api/scenarios/dimensioning', {
          method: 'PUT',
          body: JSON.stringify({ name: dimensioningScenario.name || 'Dimensionado WFM', payload: dimensioningScenario.payload }),
        }),
      ]);
      setStatus('Escenario guardado en SQLite.');
      setTimeout(() => setStatus(''), 3500);
    } catch (err) {
      setError(err.message);
    }
  };

  const resetDefaults = async () => {
    try {
      setError('');
      const result = await api('/api/reset-demo', { method: 'POST' });
      await reloadAll();
      setStatus(result.message || 'Valores del examen restaurados.');
      setTimeout(() => setStatus(''), 3500);
    } catch (err) {
      setError(err.message);
    }
  };

  const ActiveIcon = useMemo(() => tabs.find((tab) => tab.id === active)?.icon || Calculator, [active]);

  return (
    <div className="app">
      <aside>
        <div className="brand">
          <div className="brand-icon"><ActiveIcon size={24} /></div>
          <div>
            <h1>Calculadora WFM</h1>
            <p>Basada en Examen Planeamiento</p>
          </div>
        </div>
        <nav>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} className={active === tab.id ? 'active' : ''} onClick={() => setActive(tab.id)}>
                <Icon size={18} /> {tab.label}
              </button>
            );
          })}
        </nav>
        <div className="aside-note">
          <b>Default del examen</b>
          <span>Los valores originales se cargan solos al abrir la web. Puedes editarlos, guardarlos o restaurarlos.</span>
        </div>
        <div className="aside-note muted-note">
          <b>Coolify</b>
          <span>Un solo Docker container, SQLite persistente en /data.</span>
        </div>
      </aside>

      <main>
        <header>
          <div>
            <span className="eyebrow">Examen Planeamiento</span>
            <h2>{tabs.find((tab) => tab.id === active)?.label}</h2>
          </div>
          <button className="secondary" onClick={reloadAll}><RefreshCcw size={16} /> Actualizar</button>
        </header>

        {error && <div className="error">{error}</div>}

        {active === 'calculator' && (
          <CalculatorPage
            exercisesScenario={exercisesScenario}
            dimensioningScenario={dimensioningScenario}
            setExercisesScenario={setExercisesScenario}
            setDimensioningScenario={setDimensioningScenario}
            exerciseResult={exerciseResult}
            dimensioningResult={dimensioningResult}
            saveAll={saveAll}
            resetDefaults={resetDefaults}
            status={status}
          />
        )}
        {active === 'case' && <CaseStudyPage analytics={analytics} />}
        {active === 'imports' && <ImportPage records={records} reloadAll={reloadAll} resetDefaults={resetDefaults} />}
      </main>
    </div>
  );
}
