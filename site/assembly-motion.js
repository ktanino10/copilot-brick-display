export function explosionOffset(instance, model, message, amount) {
  if (!Number.isFinite(amount) || amount < 0 || amount > 1) {
    throw new RangeError('Explosion amount must be between 0 and 1.');
  }
  if (amount === 0) return [0, 0, 0];
  const presentation = model.presentation;
  if (!presentation || message.interface_id !== 'BASE-FRONT-NP3') {
    throw new Error('The current exploded view requires the five-course NP3 front interface.');
  }
  const ramp = (start, end) => Math.min(1, Math.max(0, (amount - start) / (end - start)));
  const spread = ramp(.4, 1);
  const centerLayer = (model.body_courses + model.base_courses) / 2;
  const baseOffset = -centerLayer * presentation.exploded_course_gap_mm * spread;
  if (instance.role === 'keeper') {
    const topCourseOffset = (model.base_courses - 1 - centerLayer)
      * presentation.exploded_course_gap_mm * spread;
    return [0, -ramp(.08, .15) * presentation.keeper_forward_mm,
      topCourseOffset + ramp(0, .08) * presentation.keeper_release_mm + spread * 18];
  }
  if (instance.role === 'front_module') {
    const lift = ramp(.15, .3) * presentation.plaque_release_mm;
    const forward = ramp(.3, .4) * presentation.plaque_front_clearance_mm;
    return [0, forward ? -forward : 0, baseOffset + lift * (1 - spread)
      - presentation.plaque_display_drop_mm * spread];
  }
  const layer = instance.position[2] / 9.6;
  return [0, 0, (layer - centerLayer) * presentation.exploded_course_gap_mm * spread];
}
