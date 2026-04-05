import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const DEFAULT_APP_ROOT = path.resolve("/Users/horacedong/Desktop/Horosa-Primary Direction Trial/Horosa-Web/astrostudyui/src/components");
const OUTPUT_DIR = path.join(ROOT, "src", "horosa_skill", "knowledge", "data");

const ASTRO_CONST = {
  SUN: "Sun",
  MOON: "Moon",
  MERCURY: "Mercury",
  VENUS: "Venus",
  MARS: "Mars",
  JUPITER: "Jupiter",
  SATURN: "Saturn",
  URANUS: "Uranus",
  NEPTUNE: "Neptune",
  PLUTO: "Pluto",
  NORTH_NODE: "North Node",
  SOUTH_NODE: "South Node",
  ARIES: "Aries",
  TAURUS: "Taurus",
  GEMINI: "Gemini",
  CANCER: "Cancer",
  LEO: "Leo",
  VIRGO: "Virgo",
  LIBRA: "Libra",
  SCORPIO: "Scorpio",
  SAGITTARIUS: "Sagittarius",
  CAPRICORN: "Capricorn",
  AQUARIUS: "Aquarius",
  PISCES: "Pisces",
  HOUSE1: "House1",
  HOUSE2: "House2",
  HOUSE3: "House3",
  HOUSE4: "House4",
  HOUSE5: "House5",
  HOUSE6: "House6",
  HOUSE7: "House7",
  HOUSE8: "House8",
  HOUSE9: "House9",
  HOUSE10: "House10",
  HOUSE11: "House11",
  HOUSE12: "House12",
  PARS_FORTUNA: "Pars Fortuna",
  PARS_SPIRIT: "Pars Spirit",
  PARS_VENUS: "Pars Venus",
  PARS_MERCURY: "Pars Mercury",
  PARS_MARS: "Pars Mars",
  PARS_JUPITER: "Pars Jupiter",
  PARS_SATURN: "Pars Saturn",
  PARS_FATHER: "Pars Father",
  PARS_MOTHER: "Pars Mother",
  PARS_BROTHERS: "Pars Brothers",
  PARS_WEDDING_MALE: "Pars Wedding [Male]",
  PARS_WEDDING_FEMALE: "Pars Wedding [Female]",
  PARS_SONS: "Pars Sons",
  PARS_DISEASES: "Pars Diseases",
  PARS_LIFE: "Pars Life",
  PARS_RADIX: "Pars Radix",
};

const ASTRO_CN = {
  Sun: "太阳",
  Moon: "月亮",
  Mercury: "水星",
  Venus: "金星",
  Mars: "火星",
  Jupiter: "木星",
  Saturn: "土星",
  Uranus: "天王星",
  Neptune: "海王星",
  Pluto: "冥王星",
  "North Node": "北交",
  "South Node": "南交",
  Aries: "牡羊",
  Taurus: "金牛",
  Gemini: "双子",
  Cancer: "巨蟹",
  Leo: "狮子",
  Virgo: "室女",
  Libra: "天秤",
  Scorpio: "天蝎",
  Sagittarius: "射手",
  Capricorn: "摩羯",
  Aquarius: "宝瓶",
  Pisces: "双鱼",
  "Pars Fortuna": "福点",
  "Pars Spirit": "灵点",
  "Pars Venus": "爱点",
  "Pars Mercury": "弱点",
  "Pars Mars": "勇点",
  "Pars Jupiter": "赢点",
  "Pars Saturn": "罪点",
  "Pars Father": "父权点",
  "Pars Mother": "母爱点",
  "Pars Brothers": "友情点",
  "Pars Wedding [Male]": "婚姻点（男性）",
  "Pars Wedding [Female]": "婚姻点（女性）",
  "Pars Sons": "子嗣点",
  "Pars Diseases": "灾厄点",
  "Pars Life": "生命点",
  "Pars Radix": "光耀点",
};

const ASTRO_KEYS = {
  planet: [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "North Node",
    "South Node",
  ],
  sign: [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
  ],
  house: Array.from({ length: 12 }, (_, index) => `House${index + 1}`),
  lot: [
    "Pars Fortuna",
    "Pars Spirit",
    "Pars Venus",
    "Pars Mercury",
    "Pars Mars",
    "Pars Jupiter",
    "Pars Saturn",
    "Pars Father",
    "Pars Mother",
    "Pars Brothers",
    "Pars Wedding [Male]",
    "Pars Wedding [Female]",
    "Pars Sons",
    "Pars Diseases",
    "Pars Life",
    "Pars Radix",
  ],
  aspect: [0, 30, 45, 60, 90, 120, 135, 150, 180],
};

function loadModule(filePath, exportExpression, contextExtras = {}) {
  let code = fs.readFileSync(filePath, "utf8");
  code = code.replace(/^import .*$/gm, "");
  code = code.replace(/export function /g, "function ");
  const context = vm.createContext({
    console,
    ...contextExtras,
  });
  context.globalThis = context;
  vm.runInContext(`${code}\n;globalThis.__bundle = ${exportExpression};`, context, { filename: filePath });
  return context.__bundle;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function writeJson(filePath, payload) {
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf8");
}

function buildAstroBundle(appRoot) {
  const astroFile = path.join(appRoot, "astro", "AstroMeaningData.js");
  const astro = loadModule(
    astroFile,
    "{ buildMeaningTipByCategory, buildAspectMeaningTip }",
    {
      AstroConst: ASTRO_CONST,
      AstroText: { AstroMsgCN: ASTRO_CN, AstroTxtMsg: ASTRO_CN },
    },
  );
  const categories = {};
  for (const [category, keys] of Object.entries(ASTRO_KEYS)) {
    categories[category] = {};
    for (const key of keys) {
      const entry =
        category === "aspect"
          ? astro.buildAspectMeaningTip(key)
          : astro.buildMeaningTipByCategory(category, key);
      if (entry) {
        categories[category][String(key)] = entry;
      }
    }
  }
  return {
    source: astroFile,
    generated_at: new Date().toISOString(),
    labels: ASTRO_CN,
    categories,
  };
}

function buildLiuRengBundle(appRoot) {
  const filePath = path.join(appRoot, "liureng", "LRShenJiangDoc.js");
  const liureng = loadModule(
    filePath,
    "{ SHEN_INFO, JIANG_INFO, JIANG_ALIASES, JIANG_BRANCH_NOTE, buildLiuRengShenTipObj, normalizeLiuRengJiangName }",
  );
  const shenEntries = {};
  for (const branch of Object.keys(liureng.SHEN_INFO)) {
    shenEntries[branch] = liureng.buildLiuRengShenTipObj(branch);
  }
  return {
    source: filePath,
    generated_at: new Date().toISOString(),
    shen_entries: shenEntries,
    shen_info: liureng.SHEN_INFO,
    jiang_info: liureng.JIANG_INFO,
    jiang_aliases: liureng.JIANG_ALIASES,
    jiang_branch_note: liureng.JIANG_BRANCH_NOTE,
  };
}

function buildQimenBundle(appRoot) {
  const filePath = path.join(appRoot, "dunjia", "QimenXiangDoc.js");
  const qimen = loadModule(
    filePath,
    "{ QIMEN_DOC, buildQimenXiangTipObj }",
  );
  const categories = {};
  for (const category of ["stem", "door", "star", "god"]) {
    categories[category] = {};
    for (const key of Object.keys(qimen.QIMEN_DOC[category] || {})) {
      categories[category][key] = qimen.buildQimenXiangTipObj(category, key);
    }
  }
  return {
    source: filePath,
    generated_at: new Date().toISOString(),
    raw_text: qimen.QIMEN_DOC.rawText,
    categories,
  };
}

function main() {
  const appRoot = process.argv[2] ? path.resolve(process.argv[2]) : DEFAULT_APP_ROOT;
  ensureDir(OUTPUT_DIR);
  writeJson(path.join(OUTPUT_DIR, "astro.json"), buildAstroBundle(appRoot));
  writeJson(path.join(OUTPUT_DIR, "liureng.json"), buildLiuRengBundle(appRoot));
  writeJson(path.join(OUTPUT_DIR, "qimen.json"), buildQimenBundle(appRoot));
  console.log(JSON.stringify({ ok: true, output_dir: OUTPUT_DIR, app_root: appRoot }, null, 2));
}

main();
