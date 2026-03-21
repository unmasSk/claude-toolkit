/**
 * Random adjective-animal room name generator.
 * Produces slug-safe names like "powerful-salamander" or "silent-falcon".
 */

const ADJECTIVES = [
  'ancient', 'brave', 'cosmic', 'dark', 'electric',
  'fierce', 'frozen', 'golden', 'hollow', 'iron',
  'jade', 'keen', 'lunar', 'mystic', 'neon',
  'noble', 'phantom', 'rugged', 'savage', 'silent',
  'swift', 'thunder', 'vivid', 'wild', 'amber',
];

const ANIMALS = [
  'salamander', 'falcon', 'jaguar', 'raven', 'wolf',
  'cobra', 'eagle', 'fox', 'hawk', 'lion',
  'lynx', 'mole', 'pike', 'shark', 'stag',
  'swan', 'tiger', 'bear', 'crow', 'deer',
  'elk', 'ibis', 'jay', 'kite', 'ram',
];

function pick(arr: readonly string[]): string {
  return arr[Math.floor(Math.random() * arr.length)]!;
}

export function generateRoomName(): string {
  return `${pick(ADJECTIVES)}-${pick(ANIMALS)}`;
}
