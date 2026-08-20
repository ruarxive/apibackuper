import React from 'react';
import Link from '@docusaurus/Link';
import styles from './DocsContents.module.css';

const sections = [
  {
    title: 'Getting Started',
    to: '/getting-started/installation',
    description:
      'Install apibackuper and complete a first estimate, backup, and export.',
    links: [
      {label: 'Installation', to: '/getting-started/installation'},
      {label: 'Quick start', to: '/getting-started/quick-start'},
      {label: 'When to use', to: '/getting-started/when-to-use'},
      {label: 'Cookbook', to: '/getting-started/cookbook'},
      {label: 'Basic usage', to: '/getting-started/basic-usage'},
      {label: 'Troubleshooting', to: '/getting-started/troubleshooting'},
      {label: 'Best practices', to: '/getting-started/best-practices'},
    ],
  },
  {
    title: 'Use Cases',
    to: '/use-cases/rest-api-backup',
    description:
      'End-to-end examples for full backups, incremental updates, follow requests, and exports.',
    links: [
      {label: 'REST API backup', to: '/use-cases/rest-api-backup'},
      {label: 'Incremental and update', to: '/use-cases/incremental-and-update'},
      {label: 'Follow and files', to: '/use-cases/follow-and-files'},
      {label: 'Export and storage', to: '/use-cases/export-and-storage'},
      {label: 'Protected APIs', to: '/use-cases/protected-apis'},
    ],
  },
  {
    title: 'CLI Reference',
    to: '/commands/',
    description:
      'Command-by-command reference for create, run, export, follow, and more.',
    links: [
      {label: 'All commands', to: '/commands/'},
      {label: 'create', to: '/commands/create'},
      {label: 'run', to: '/commands/run'},
      {label: 'estimate', to: '/commands/estimate'},
      {label: 'export', to: '/commands/export'},
      {label: 'follow', to: '/commands/follow'},
      {label: 'detect', to: '/commands/detect'},
    ],
  },
  {
    title: 'Configuration',
    to: '/configuration/',
    description:
      'YAML and INI project files: pagination, auth, storage, hooks, and rate limits.',
    links: [
      {label: 'Configuration overview', to: '/configuration/'},
      {label: 'Pagination', to: '/configuration/pagination'},
      {label: 'Authentication', to: '/configuration/auth'},
      {label: 'Storage', to: '/configuration/storage'},
      {label: 'Hooks', to: '/configuration/hooks'},
      {label: 'Full reference', to: '/configuration/reference'},
    ],
  },
  {
    title: 'Examples',
    to: '/examples/',
    description:
      'Working projects, starter templates, and feature-focused samples.',
    links: [
      {label: 'Example projects', to: '/examples/'},
      {label: 'Templates', to: '/examples/templates'},
      {label: 'Feature examples', to: '/examples/feature-examples'},
    ],
  },
  {
    title: 'Development',
    to: '/development/contributing',
    description: 'Contributing, tests, community, and license.',
    links: [
      {label: 'Contributing', to: '/development/contributing'},
      {label: 'Community', to: '/development/community'},
      {label: 'License', to: '/license'},
    ],
  },
];

function Section({title, to, description, links}) {
  return (
    <article className={styles.card}>
      <h3 className={styles.cardTitle}>
        <Link to={to}>{title}</Link>
      </h3>
      <p className={styles.cardDescription}>{description}</p>
      <ul className={styles.linkList}>
        {links.map((item) => (
          <li key={item.label}>
            {item.href ? (
              <a href={item.href}>{item.label}</a>
            ) : (
              <Link to={item.to}>{item.label}</Link>
            )}
          </li>
        ))}
      </ul>
    </article>
  );
}

export default function DocsContents() {
  return (
    <section className={styles.contents}>
      <div className="container">
        <h2 className={styles.heading}>Documentation contents</h2>
        <p className={styles.intro}>
          Start with a section below, or use the sidebar from any page. The CLI
          entry point is <code>apibackuper</code>.
        </p>
        <div className={styles.grid}>
          {sections.map((section) => (
            <Section key={section.title} {...section} />
          ))}
        </div>
      </div>
    </section>
  );
}
