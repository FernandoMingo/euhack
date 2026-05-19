/**
 * Five Rotterdam events used as seed data for the resident map screen.
 * These power the prototype UX while the backend matching engine
 * isn't producing live invitations yet.
 */

export interface DemoEvent {
  id: string;
  title: string;
  type: string;
  latitude: number;
  longitude: number;
  dateLabel: string;
  timeLabel: string;
  location: string;
  groupSize: number;
  pace: string;
  host: string;
  cost: string;
  accessibility: string;
  whyFit: string;
  description: string;
  whatToExpect: string;
}

export const demoEvents: DemoEvent[] = [
  {
    id: "ev-kralingse",
    title: "Saturday morning walk",
    type: "Outdoor · neighbourhood walk",
    latitude: 51.9298,
    longitude: 4.5085,
    dateLabel: "Sat",
    timeLabel: "10:00 – 11:30",
    location: "Kralingse Bos",
    groupSize: 4,
    pace: "Calm",
    host: "Maya",
    cost: "Free",
    accessibility: "Step-free route",
    whyFit: "You said you like calm outdoor activities and small groups.",
    description:
      "A quiet loop around the lake at Kralingse Bos with four other residents who like calm, low-pressure outdoor mornings.",
    whatToExpect:
      "Maya meets everyone at the kiosk near the south entrance. There's no fixed pace and no group photos — just a slow walk with coffee at the end if anyone wants to stay.",
  },
  {
    id: "ev-boijmans",
    title: "Museum coffee meetup",
    type: "Cultural · café",
    latitude: 51.9143,
    longitude: 4.4750,
    dateLabel: "Sun",
    timeLabel: "11:00 – 12:30",
    location: "Museum Boijmans Van Beuningen",
    groupSize: 3,
    pace: "Gentle",
    host: "Ravi",
    cost: "Free entry",
    accessibility: "Step-free, seating available",
    whyFit: "Quiet indoor space, museum context, small group.",
    description: "Coffee in the museum café and an optional unhurried walk through one gallery.",
    whatToExpect:
      "Ravi finds the group in the café near the entrance. People can choose to stay for the gallery or leave after coffee — no expectation either way.",
  },
  {
    id: "ev-essenburgpark",
    title: "Community garden visit",
    type: "Gardening · outdoor",
    latitude: 51.9275,
    longitude: 4.4527,
    dateLabel: "Sun",
    timeLabel: "14:00 – 15:30",
    location: "Essenburgpark",
    groupSize: 5,
    pace: "Hands-on",
    host: "Lin",
    cost: "Free",
    accessibility: "Step-free, host present",
    whyFit: "Small hands-on group, outdoor activity, gardening interest.",
    description: "Help tend the herb beds and meet the regular gardeners.",
    whatToExpect:
      "Lin shows everyone the bed they're tending today. Tools and gloves provided. Tea afterwards on the picnic table.",
  },
  {
    id: "ev-bibliotheek",
    title: "Library board game evening",
    type: "Games · indoor",
    latitude: 51.9216,
    longitude: 4.4847,
    dateLabel: "Wed",
    timeLabel: "19:00 – 21:00",
    location: "Centrale Bibliotheek",
    groupSize: 6,
    pace: "Relaxed",
    host: "Ravi",
    cost: "Free",
    accessibility: "Step-free, quiet space",
    whyFit: "Small indoor group, no alcohol, low social-energy.",
    description: "Casual board games at the library on the upper floor.",
    whatToExpect:
      "Six people, two tables. No tournaments, no scoring. Bring nothing — the library has the games.",
  },
  {
    id: "ev-kop",
    title: "Photography walk",
    type: "Photography · outdoor",
    latitude: 51.9028,
    longitude: 4.4892,
    dateLabel: "Sat",
    timeLabel: "13:00 – 15:00",
    location: "Kop van Zuid",
    groupSize: 5,
    pace: "Calm",
    host: "Maya",
    cost: "Free",
    accessibility: "Step-free route",
    whyFit: "Photography interest, parks, small group, calm pace.",
    description: "A waterfront walk along Kop van Zuid with five other amateur photographers.",
    whatToExpect:
      "Bring whatever camera you have, including phone. Maya meets at Wilhelminapier. No assignments — just walk and notice what you like.",
  },
];
