import { PageHead } from './ui.jsx';

// What was measured, what was not, and how personal data is handled. Every number here comes from the detector project's measurement
// scripts (docs/ACCURACY_MEASURED.md); nothing is rounded up and nothing unmeasured is claimed.
const Row = ({ a, b }) => <tr><td>{a}</td><td>{b}</td></tr>;

export function AccuracyPage({ standalone = false }) {
  return (
    <>
      <PageHead title="About accuracy and privacy" sub="What SiteGuard measured, what it cannot do, and how personal data is handled." />
      {standalone && <p className="small"><a href="/">Back to sign in</a></p>}
      <div className="note info">Nothing here is a promise of 99.99%. No camera system can honestly promise that. These are the figures this one reached on photos and clips it was not trained on. A catch is only an alert until a supervisor confirms it.</div>

      <section className="card">
        <h3>What was measured</h3>
        <div className="scroll"><table>
          <thead><tr><th>Check</th><th>Result</th></tr></thead>
          <tbody>
            <Row a="Finding things in 314 held-out photos (AP at IoU 0.5)" b="person 92.5%, helmet 94.1%, vest 90.1%, bare head 73.6%; mean 87.6%" />
            <Row a={'"No helmet" on 661 labelled workers (60 px or taller)'} b="precision 91.8% (of those flagged, this many really had none); caught automatically 81.2%; 95.8% caught or sent to review" />
            <Row a="Workers the detector never found" b="about 12.9% on normal photos" />
            <Row a="Vest worn, wrongly flagged as missing" b="4.2% of people who wore one" />
            <Row a="Missing vest (101 photos, 78 workers without one)" b="69.2% caught automatically; 91% caught or sent to review" />
            <Row a="Dark photos (darkened copies of the test photos: simulated)" b={'"no helmet" precision 89.0%; 18.9% of workers not found; 97.7% caught or sent to review'} />
            <Row a="Worker-down alert, per clip (160 clips, 4 people)" b="53% of falls caught (24% in low light); a false alarm on 7% of normal clips. Weak." />
            <Row a="Face recognition (160 clips, 4 people)" b="no two people merged; 64 of 64 named sightings right; about 20% of faces left unnamed" />
          </tbody>
        </table></div>
      </section>

      <section className="card">
        <h3>What it cannot do</h3>
        <ul style={{ margin: '0 0 0 1.2rem' }}>
          <li>It cannot tell why a worker is on the ground: a trip, a heart attack and an object that fell all look the same. It says a worker is down, and a person must go and check.</li>
          <li>The falling-object watch uses motion only and needs a fixed camera. It cannot tell a crane lowering a load on purpose from a drop, so it warns whenever something large descends near a worker. It has been tried on one real clip and synthetic ones, not measured on a set.</li>
          <li>A worker who is a dark silhouette against a bright background cannot be judged. These are sent to review, never recorded as a violation.</li>
          <li>Gloves, boots and goggles use a second model whose accuracy has not been measured. Hi-vis shirts and life jackets are not trained.</li>
          <li>Faces narrower than about 48 pixels cannot be recognised. Someone whose face is unclear gets a made-up name for that footage only, which does not mean the system knows who they are.</li>
          <li>The live camera and the spoken and siren alerts have been tried on the demo, not on a real site.</li>
        </ul>
      </section>

      <section className="card">
        <h3>How decisions are made</h3>
        <ul style={{ margin: '0 0 0 1.2rem' }}>
          <li>Nothing counts against a person until a supervisor confirms it. Penalties are only proposed by the system: three confirmed violations in 30 days propose one (an example of INR 500). A supervisor approves or waives it, and the employee can dispute it.</li>
          <li>One violation is counted per person per day. Being caught again the same day only raises the catch count.</li>
          <li>People caught are told by a spoken alert at most once every 10 minutes, and only people who broke a rule are named.</li>
        </ul>
      </section>

      <section className="card">
        <h3>Privacy</h3>
        <ul style={{ margin: '0 0 0 1.2rem' }}>
          <li>A face is used for recognition only with the person's consent, ticked by the supervisor who adds the photo.</li>
          <li>Only a numeric face template is kept for recognition, never the photo. A profile photo, if added, is shown on the person's own pages and can be removed.</li>
          <li>A person's template can be removed at any time. Passwords are stored hashed and are shown only once, when an account is made.</li>
          <li>Each supervisor sees only their own site. An employee sees only their own record.</li>
          <li>The names, IDs, salaries and pictures in this demo are made up. Real use needs the company's own policy and notice under the Digital Personal Data Protection Act, 2023.</li>
        </ul>
      </section>
    </>
  );
}
