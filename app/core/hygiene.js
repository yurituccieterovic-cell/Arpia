/**
 * ISA Hygiene — varredura horária do grafo de conhecimento (Assembleias #392 #398 #404)
 * ISA avalia "saúde" das conexões do terrário virtual a cada hora.
 * Nós isolados sem commits ou interações por >3 períodos de assembleia → stale:true.
 * Dispara minuta de e-mail de alerta ao conselho administrativo.
 * ISA NUNCA executa DELETE sozinha.
 */

const { Pool } = require("pg");
const nodemailer = require("nodemailer");

const STALE_THRESHOLD_PERIODS = 3;   // períodos de assembleia sem atividade
const ASSEMBLY_PERIOD_HOURS = 1;      // 1 hora por período (cron: 0 * * * *)
const STALE_HOURS = STALE_THRESHOLD_PERIODS * ASSEMBLY_PERIOD_HOURS;

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function getTransporter() {
  return nodemailer.createTransporter({
    service: "gmail",
    auth: {
      user: process.env.GMAIL_ACCOUNT,
      pass: process.env.GMAIL_APP_PASSWORD,
    },
  });
}

/**
 * Varre tabelas: conversations, eco_logs, user_sessions (e fauna_nodes)
 * Identifica nós sem atividade > STALE_HOURS.
 */
async function sweepStaleNodes() {
  const client = await pool.connect();
  try {
    // Qualisignos sem Sinsigno recente
    const { rows: staleSignos } = await client.query(`
      SELECT q.id, q.nome, q.eixo, q.face_id,
             MAX(s.created_at) AS ultimo_sinsigno
      FROM qualisignos q
      LEFT JOIN sinsignos s ON s.qualisigno_id = q.id
      GROUP BY q.id, q.nome, q.eixo, q.face_id
      HAVING MAX(s.created_at) < NOW() - INTERVAL '${STALE_HOURS} hours'
          OR MAX(s.created_at) IS NULL
    `);

    // Tasks isoladas (sem relação de entrada/saída)
    const { rows: staleTasks } = await client.query(`
      SELECT t.id, t.title, t.status, t.created_at
      FROM tasks t
      WHERE t.id NOT IN (
        SELECT from_id FROM task_relations
        UNION
        SELECT to_id FROM task_relations
      )
      AND t.created_at < NOW() - INTERVAL '${STALE_HOURS} hours'
      AND t.status NOT IN ('done', 'archived')
    `);

    // Fauna nodes sem atualização
    const { rows: staleNodes } = await client.query(`
      SELECT id, specie_name, updated_at
      FROM fauna_nodes
      WHERE updated_at < NOW() - INTERVAL '${STALE_HOURS} hours'
    `).catch(() => ({ rows: [] }));

    return { staleSignos, staleTasks, staleNodes };
  } finally {
    client.release();
  }
}

/**
 * Marca nós stale no banco — jamais deleta.
 * Usa UPSERT para não sobrescrever dados existentes.
 */
async function markStale(staleData) {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");

    for (const task of staleData.staleTasks) {
      await client.query(
        `UPDATE tasks SET status = 'stale'
         WHERE id = $1 AND status NOT IN ('done', 'archived', 'stale')`,
        [task.id]
      );
    }

    // Registra evento de auditoria no canal ISA
    const staleCount =
      staleData.staleSignos.length +
      staleData.staleTasks.length +
      staleData.staleNodes.length;

    if (staleCount > 0) {
      await client.query(
        `INSERT INTO sinsignos (qualisigno_id, command_log, device_id, source)
         VALUES (1, $1, 'ISA-HYGIENE', 'isa')`,
        [`#ISA:STALE:${staleCount}:${new Date().toISOString()}`]
      ).catch(() => null);  // graceful — tabela pode não ter qualisigno_id=1
    }

    await client.query("COMMIT");
    return staleCount;
  } catch (e) {
    await client.query("ROLLBACK");
    throw e;
  } finally {
    client.release();
  }
}

/**
 * Envia minuta de e-mail ao conselho quando stale_count > 0.
 */
async function notifyCouncil(staleData, staleCount) {
  if (staleCount === 0) return;

  const transporter = await getTransporter();
  const linhas = [
    `[ISA HYGIENE] ${new Date().toISOString()}`,
    `Nós stale detectados: ${staleCount}`,
    "",
    "== QUALISIGNOS ==",
    ...staleData.staleSignos.map(s =>
      `  ID${s.id} face_id=${s.face_id} nome=${s.nome} último_sinsigno=${s.ultimo_sinsigno ?? "NUNCA"}`
    ),
    "",
    "== TASKS ISOLADAS ==",
    ...staleData.staleTasks.map(t =>
      `  ID${t.id} "${t.title}" status=${t.status} criada=${t.created_at}`
    ),
    "",
    "== FAUNA NODES ==",
    ...staleData.staleNodes.map(n =>
      `  ID${n.id} ${n.specie_name} última_atualização=${n.updated_at}`
    ),
    "",
    "ISA não executou DELETE. Ação requerida do conselho em até 7 dias.",
    "Após 7 dias sem resposta → flag requires_human_review=true.",
  ].join("\n");

  await transporter.sendMail({
    from: process.env.GMAIL_ACCOUNT,
    to: process.env.GMAIL_ACCOUNT,
    subject: `[ISA] ${staleCount} nós stale — ação requerida`,
    text: linhas,
  });
}

/**
 * Entry point — executado pelo cron `0 * * * *`
 */
async function runHygieneCycle() {
  console.log(`[ISA] Iniciando ciclo de higiene: ${new Date().toISOString()}`);
  try {
    const staleData = await sweepStaleNodes();
    const staleCount = await markStale(staleData);
    await notifyCouncil(staleData, staleCount);
    console.log(`[ISA] Ciclo concluído. Stale: ${staleCount}`);
    return { staleCount, ...staleData };
  } catch (err) {
    console.error("[ISA] Erro no ciclo de higiene:", err);
    throw err;
  }
}

module.exports = { runHygieneCycle, sweepStaleNodes, markStale };

// Execução standalone: node hygiene.js
if (require.main === module) {
  runHygieneCycle()
    .then(r => { console.log("Resultado:", JSON.stringify(r, null, 2)); process.exit(0); })
    .catch(e => { console.error(e); process.exit(1); });
}
