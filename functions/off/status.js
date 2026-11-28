/** GET /off/status: is sharing switched on, and to the real or the test site? (No secrets.) */
import { account, json, target } from './_shared.js';
export const onRequestGet = ({ env }) => json(200, { on: !!account(env), live: target(env).live });
