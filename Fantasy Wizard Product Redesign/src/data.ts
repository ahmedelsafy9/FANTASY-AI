export type Player = {
  id: number
  name: string
  club: string
  position: string
  points: number | null
  status: string
  fixture: string
  price: number
  ownership: number
  photo: string
}
export const scenario = { completed: 5, target: 6, season: "2024/25" }
const portrait = (id: string) =>
  `https://resources.premierleague.com/premierleague/photos/players/250x250/p${id}.png`
export const players: Player[] = [
  {
    id: 1,
    name: "Erling Haaland",
    club: "Man City",
    position: "FWD",
    points: 8.6,
    status: "Available",
    fixture: "NEW (A)",
    price: 15.3,
    ownership: 68.2,
    photo: portrait("223094"),
  },
  {
    id: 2,
    name: "Mohamed Salah",
    club: "Liverpool",
    position: "MID",
    points: 8.1,
    status: "Available",
    fixture: "WOL (A)",
    price: 12.8,
    ownership: 42.1,
    photo: portrait("118748"),
  },
  {
    id: 3,
    name: "Bukayo Saka",
    club: "Arsenal",
    position: "MID",
    points: 7.4,
    status: "Available",
    fixture: "LEI (H)",
    price: 10.0,
    ownership: 31.5,
    photo: portrait("223340"),
  },
  {
    id: 4,
    name: "Cole Palmer",
    club: "Chelsea",
    position: "MID",
    points: 6.8,
    status: "Available",
    fixture: "BHA (H)",
    price: 10.6,
    ownership: 24.8,
    photo: portrait("244851"),
  },
  {
    id: 5,
    name: "Ollie Watkins",
    club: "Aston Villa",
    position: "FWD",
    points: 6.5,
    status: "Available",
    fixture: "IPS (A)",
    price: 9.0,
    ownership: 18.4,
    photo: portrait("178301"),
  },
  {
    id: 6,
    name: "Son Heung-min",
    club: "Spurs",
    position: "MID",
    points: 5.8,
    status: "Doubtful",
    fixture: "MUN (A)",
    price: 10.0,
    ownership: 7.6,
    photo: portrait("85971"),
  },
  {
    id: 7,
    name: "Gabriel",
    club: "Arsenal",
    position: "DEF",
    points: 5.7,
    status: "Available",
    fixture: "LEI (H)",
    price: 6.1,
    ownership: 20.2,
    photo: portrait("226597"),
  },
  {
    id: 8,
    name: "Trent Alexander-Arnold",
    club: "Liverpool",
    position: "DEF",
    points: 5.5,
    status: "Available",
    fixture: "WOL (A)",
    price: 7.0,
    ownership: 25.0,
    photo: portrait("169187"),
  },
  {
    id: 9,
    name: "David Raya",
    club: "Arsenal",
    position: "GK",
    points: 4.5,
    status: "Doubtful",
    fixture: "LEI (H)",
    price: 5.6,
    ownership: 25.1,
    photo: portrait("154561"),
  },
  {
    id: 10,
    name: "Dean Henderson",
    club: "Crystal Palace",
    position: "GK",
    points: 3.5,
    status: "Available",
    fixture: "EVE (A)",
    price: 4.5,
    ownership: 12.0,
    photo: portrait("172649"),
  },
  {
    id: 11,
    name: "Pedro Porro",
    club: "Spurs",
    position: "DEF",
    points: 4.3,
    status: "Available",
    fixture: "MUN (A)",
    price: 5.5,
    ownership: 23.0,
    photo: portrait("441164"),
  },
  {
    id: 12,
    name: "Ezri Konsa",
    club: "Aston Villa",
    position: "DEF",
    points: 4.1,
    status: "Available",
    fixture: "IPS (A)",
    price: 4.5,
    ownership: 8.2,
    photo: portrait("199796"),
  },
  {
    id: 13,
    name: "João Pedro",
    club: "Brighton",
    position: "FWD",
    points: null,
    status: "Injured",
    fixture: "CHE (A)",
    price: 5.6,
    ownership: 15.5,
    photo: portrait("475168"),
  },
  {
    id: 14,
    name: "Eberechi Eze",
    club: "Crystal Palace",
    position: "MID",
    points: 5.2,
    status: "Available",
    fixture: "EVE (A)",
    price: 6.9,
    ownership: 9.1,
    photo: portrait("232413"),
  },
  {
    id: 15,
    name: "Taylor Harwood-Bellis",
    club: "Southampton",
    position: "DEF",
    points: 2.5,
    status: "Unknown",
    fixture: "BOU (A)",
    price: 4.0,
    ownership: 5.3,
    photo: portrait("450527"),
  },
]
export const matches = [
  {
    home: "Newcastle",
    away: "Man City",
    short: ["NEW", "MCI"],
    crests: [4, 43],
    probabilities: [19, 23, 58],
    time: "SAT 28 SEP · 12:30",
    venue: "St. James’ Park",
  },
  {
    home: "Arsenal",
    away: "Leicester",
    short: ["ARS", "LEI"],
    crests: [3, 13],
    probabilities: [76, 16, 8],
    time: "SAT 28 SEP · 15:00",
    venue: "Emirates Stadium",
  },
  {
    home: "Chelsea",
    away: "Brighton",
    short: ["CHE", "BHA"],
    crests: [8, 36],
    probabilities: [52, 25, 23],
    time: "SAT 28 SEP · 15:00",
    venue: "Stamford Bridge",
  },
  {
    home: "Wolves",
    away: "Liverpool",
    short: ["WOL", "LIV"],
    crests: [39, 14],
    probabilities: [14, 21, 65],
    time: "SAT 28 SEP · 17:30",
    venue: "Molineux Stadium",
  },
  {
    home: "Man United",
    away: "Spurs",
    short: ["MUN", "TOT"],
    crests: [1, 6],
    probabilities: [38, 27, 35],
    time: "SUN 29 SEP · 16:30",
    venue: "Old Trafford",
  },
]
export type Match = {
  home: string
  away: string
  short: string[]
  crests: number[]
  probabilities: number[]
  time: string
  venue: string
  homeCrest?: string
  awayCrest?: string
  key?: number
}
