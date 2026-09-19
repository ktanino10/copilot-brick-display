export function explosionOffset(instance, model, message, amount) {
  if (!Number.isFinite(amount) || amount < 0 || amount > 1) {
    throw new RangeError('Explosion amount must be between 0 and 1.');
  }
  if (instance.part !== 'MSG-CARD') return [0, 0, (instance.step - 1) * 3 * amount];
  const dock = model.placements.find((item) => item.part === 'MSG-DOCK');
  if (!dock) throw new Error('The message card requires a matching dock.');
  const lift = Math.min(amount / .25, 1) * (message.slot_depth + .6);
  const forward = Math.max(0, (amount - .25) / .75) * 40;
  return [0, forward > 0 ? -forward : 0, (dock.step - 1) * 3 * amount + lift];
}
