const DATA_URL = '../data/indices.json';

async function loadData() {
  const res = await fetch(DATA_URL);
  return res.json();
}

function getMonthlyByYear(monthly, year) {
  const result = Array(12).fill(null);
  monthly.filter(d => d.year === year).forEach(d => {
    result[d.month - 1] = d.close;
  });
  return result;
}

function normalizeToBase100(arr) {
  const base = arr.find(v => v != null);
  if (!base) return arr;
  return arr.map(v => v == null ? null : Math.round(v / base * 1000) / 10);
}

function getAnnualByDecade(annual, startYear) {
  const result = [];
  for (let i = 0; i < 10; i++) {
    const y = startYear + i;
    const found = annual.find(d => d.year === y);
    result.push(found ? found.close : null);
  }
  return result;
}

const INDICES = [
  { key: 'TAIEX', label: '台股 TAIEX' },
  { key: 'NASDAQ', label: '納指 NASDAQ' },
];

const MONTH_LABELS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
const YEAR_LABELS = ['Y1','Y2','Y3','Y4','Y5','Y6','Y7','Y8','Y9','Y10'];
