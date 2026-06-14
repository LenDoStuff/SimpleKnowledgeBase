import { ClipboardCheck, Clock3, FileText, HelpCircle, Network, Settings } from "lucide-react";

const icons = [FileText, Network, Clock3, ClipboardCheck, Settings];

export function SideRail() {
  return (
    <aside className="side-rail" aria-label="Application navigation">
      <div className="rail-logo">K</div>
      <nav>
        {icons.map((Icon, index) => (
          <button key={index} className={index === 0 ? "rail-button active" : "rail-button"} title={`Section ${index + 1}`}>
            <Icon size={19} />
          </button>
        ))}
      </nav>
      <button className="rail-button help" title="Help">
        <HelpCircle size={19} />
      </button>
    </aside>
  );
}

