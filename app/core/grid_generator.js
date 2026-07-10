/**
 * renderNineSquareGrid — Matriz 3×3 de tiles do ecossistema (Assembleia #403)
 * Transforma 9 caminhos de arquivo em payload bidimensional para o front-end.
 * Cada célula representa um nó visual do ecossistema (Terrário, Mesa, ISA, etc.)
 */

/**
 * @typedef {Object} GridCell
 * @property {string} path - caminho do arquivo de imagem
 * @property {number} row - linha (0-2)
 * @property {number} col - coluna (0-2)
 * @property {string} position - ex: "top-left", "center", "bottom-right"
 * @property {boolean} valid - arquivo existe e é acessível
 */

/** Rótulos dos 9 nós do ecossistema (conforme Assembleia #404 — Prompt 1) */
const NOS_ECOSSISTEMA = [
  "NÓ_INTERNO_AQUÁRIO",       // 0,0 — aquário 1m, coridoras/lebistes
  "NÓ_FRONTEIRA_TRANSIÇÃO",   // 0,1 — porta de madeira
  "NÓ_QUINTAL_ABERTO",        // 0,2 — piso de laota/tijolo
  "NÓ_ANFITEATRO_ASSEMBLEIA", // 1,0 — Assembleia Tucci / cristais
  "NÓ_MESA_NASCIMENTO_MC",    // 1,1 — berço da MC (centro)
  "NÓ_GABINETE_SUPORTE",      // 1,2 — ferramentas/solda
  "NÓ_AQUARIO_CARNÍVORO",     // 2,0 — Aruanã/Oscar/Arraia conceitual
  "NÓ_ARVORE_MEMORIA",        // 2,1 — cyber-banyan / Manga DB
  "NÓ_ISA_GUARDIAN_EYE",      // 2,2 — drone ISA / olho azul
];

const POSITION_NAMES = [
  "top-left", "top-center", "top-right",
  "mid-left", "center",     "mid-right",
  "bot-left", "bot-center", "bot-right",
];

/**
 * @param {string[]} paths - exatamente 9 caminhos de arquivo
 * @returns {{ matrix: GridCell[][], flat: GridCell[], meta: object }}
 */
function renderNineSquareGrid(paths) {
  if (!Array.isArray(paths) || paths.length !== 9) {
    throw new Error(`renderNineSquareGrid exige exatamente 9 paths — recebeu ${paths?.length ?? 0}`);
  }

  const flat = paths.map((path, idx) => ({
    path,
    row: Math.floor(idx / 3),
    col: idx % 3,
    position: POSITION_NAMES[idx],
    no_ecossistema: NOS_ECOSSISTEMA[idx],
    valid: Boolean(path && path.length > 0),
    index: idx,
  }));

  // Organiza em matriz 3×3
  const matrix = [
    flat.slice(0, 3),
    flat.slice(3, 6),
    flat.slice(6, 9),
  ];

  return {
    matrix,
    flat,
    meta: {
      total_cells: 9,
      valid_cells: flat.filter(c => c.valid).length,
      center: flat[4],              // NÓ_MESA_NASCIMENTO_MC
      guardian: flat[8],            // NÓ_ISA_GUARDIAN_EYE
      schema_version: "3x3-v1",
    },
  };
}

/**
 * Gera payload JSON pronto para o front-end PAP / SalesCockpit.
 * @param {string[]} paths
 * @returns {string}
 */
function gridToJSON(paths) {
  return JSON.stringify(renderNineSquareGrid(paths), null, 2);
}

module.exports = { renderNineSquareGrid, gridToJSON, NOS_ECOSSISTEMA };
