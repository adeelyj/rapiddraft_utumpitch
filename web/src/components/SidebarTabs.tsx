import type { ReactNode } from "react";

type SidebarTabsProps = {
  activeTab: "views" | "reviews";
  onTabChange: (tab: "views" | "reviews") => void;
  viewsPanel: ReactNode;
  reviewPanel: ReactNode;
};

const SidebarTabs = ({ activeTab, onTabChange, viewsPanel, reviewPanel }: SidebarTabsProps) => {
  return (
    <aside className="sidebar-tabs">
      <div className="sidebar-tabs__controls">
        <button
          className={`sidebar-tabs__button ${activeTab === "views" ? "sidebar-tabs__button--active" : ""}`}
          onClick={() => onTabChange("views")}
        >
          Views
        </button>
        <button
          className={`sidebar-tabs__button ${activeTab === "reviews" ? "sidebar-tabs__button--active" : ""}`}
          onClick={() => onTabChange("reviews")}
        >
          Reviews
        </button>
      </div>
      <div className="sidebar-tabs__content">{activeTab === "views" ? viewsPanel : reviewPanel}</div>
    </aside>
  );
};

export default SidebarTabs;
