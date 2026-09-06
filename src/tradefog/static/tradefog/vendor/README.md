# Third-party frontend resources

The application vendors exact upstream releases so that it can run without a
CDN or a JavaScript package manager.

| Resource | Version | License | Source |
| --- | --- | --- | --- |
| Tabler UI | 1.4.0 | MIT | https://github.com/tabler/tabler |
| htmx | 2.0.9 | 0BSD | https://github.com/bigskysoftware/htmx |
| ApexCharts | 7.0.0 | Community | https://github.com/apexcharts/apexcharts.js |
| List.js | 2.3.1 | MIT | https://github.com/javve/list.js |
| EasyMDE | 2.21.0 | MIT | https://github.com/Ionaru/easy-markdown-editor |
| DOMPurify | 3.4.14 | Apache-2.0 | https://github.com/cure53/DOMPurify |
| FsLightbox | 3.7.6 | MIT | https://github.com/banthagroup/fslightbox |
| Tabler Icons | 3.46.0 | MIT | https://github.com/tabler/tabler-icons |
| big.js | 7.0.1 | MIT | https://github.com/MikeMcl/big.js |
| Tom Select | 2.6.2 | Apache-2.0 | https://github.com/orchidjs/tom-select |

Only the selected Tabler SVG sources are stored in the package. The frontend
build creates a small sprite from them.

Tradefog configures EasyMDE without external fonts, spell-check downloads,
or image embedding. DOMPurify sanitizes its client-side Markdown preview.
