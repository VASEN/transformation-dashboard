import { CONFIG } from './config.js';

export let allProjects = [];
export let allTasks = [];
export let allTasks2026 = [];
export let allDetails = [];
export let allCurators = [];

export function setData(data) {
  allProjects = data.projects;
  allTasks = data.all_tasks || data.tasks;
  const proj2026Names = new Set(
    allProjects.filter(p => p.deadline && p.deadline.split('.')[2] === String(CONFIG.year))
               .map(p => p.name)
  );
  allTasks2026 = allTasks.filter(t => proj2026Names.has(t.project));
  allDetails = data.projects;
  allCurators = data.curators;
}
