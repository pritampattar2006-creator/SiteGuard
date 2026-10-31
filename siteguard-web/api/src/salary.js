// Monthly pay view for an employee. Only penalties a supervisor has issued (or that are paid) reduce the figure,
// and they count in the month the supervisor decided. Waived, disputed and merely proposed penalties never do.
// Whether wages may lawfully be reduced for a penalty is for HR and legal to confirm; this only shows the numbers.
export const monthKey = (date) => new Date(date).toISOString().slice(0, 7);
const DEDUCTS = ['Issued', 'Paid'];

export function payslips(monthlySalary, penalties, now = new Date(), months = 6) {
  const base = Number(monthlySalary) || 0;
  return Array.from({ length: months }, (_, i) => {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - i, 1));
    const month = d.toISOString().slice(0, 7);
    const items = penalties.filter((p) => DEDUCTS.includes(p.status) && monthKey(p.decidedAt || p.createdAt) === month);
    const deductions = items.reduce((s, p) => s + p.amount, 0);
    return { month, base, deductions, net: Math.max(0, base - deductions), items: items.map((p) => ({ id: p._id, amount: p.amount, reason: p.reason, status: p.status })) };
  });
}
