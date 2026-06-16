export const CONFIG = {
  year: 2026,
  hoursPerUnit: 1972,
  redmineBase: 'https://transformation.rm.mosreg.ru/#/issues',
};

export function applyConfig(data) {
  if (data && data.config) {
    CONFIG.year = data.config.year ?? CONFIG.year;
    CONFIG.hoursPerUnit = data.config.hours_per_unit ?? CONFIG.hoursPerUnit;
    CONFIG.redmineBase = data.config.redmine_base ?? CONFIG.redmineBase;
  }
}
