export function userId(req) {
  return JSON.parse(req.body.initDataUnsafe).user.id;
}
