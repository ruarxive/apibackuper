/**
 * Creating a sidebar enables you to:
 - create an ordered group of docs
 - render a sidebar for each doc of that group
 - provide next/previous navigation
 */

// @ts-check

/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  docs: [
    {
      type: 'link',
      label: 'Contents',
      href: '/',
    },
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/installation',
        'getting-started/quick-start',
        'getting-started/when-to-use',
        'getting-started/cookbook',
        'getting-started/basic-usage',
        'getting-started/troubleshooting',
        'getting-started/best-practices',
      ],
    },
    {
      type: 'category',
      label: 'Use Cases',
      items: [
        'use-cases/rest-api-backup',
        'use-cases/incremental-and-update',
        'use-cases/follow-and-files',
        'use-cases/export-and-storage',
        'use-cases/protected-apis',
      ],
    },
    {
      type: 'category',
      label: 'CLI Reference',
      items: [
        'commands/index',
        'commands/create',
        'commands/detect',
        'commands/estimate',
        'commands/run',
        'commands/update',
        'commands/follow',
        'commands/getfiles',
        'commands/export',
        'commands/info',
        'commands/validate-config',
      ],
    },
    {
      type: 'category',
      label: 'Configuration',
      items: [
        'configuration/index',
        'configuration/project-and-data',
        'configuration/pagination',
        'configuration/auth',
        'configuration/rate-limiting-and-requests',
        'configuration/storage',
        'configuration/follow',
        'configuration/files',
        'configuration/hooks',
        'configuration/reference',
      ],
    },
    {
      type: 'category',
      label: 'Examples',
      items: ['examples/index', 'examples/templates', 'examples/feature-examples'],
    },
    {
      type: 'category',
      label: 'Development',
      items: ['development/contributing', 'development/community'],
    },
    'license',
  ],
};

module.exports = sidebars;
