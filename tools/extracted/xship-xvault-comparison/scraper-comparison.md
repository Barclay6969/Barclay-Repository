# xShip 2026.08.31.2 vs xVault main – Scrapervergleich

| Scraper | Status | Ähnlichkeit | xShip Bytes | xVault Bytes | Zusätzliche Funktionen |
|---|---|---:|---:|---:|---|
| animetoast.py | nur xVault |  |  |  |  |
| aniworld.py | abweichend | 1.4% | 7819 | 32371 | _all_variants, _attr, _available_seasons, _dates_match, _do_login, _episode_chapter_number, _episode_title_tokens, _episode_title_variants, _episode_titles_match, _external_redirect_target, _extract_episode_title, _extract_publish_date, _find_matching_episode_page, _getLogin, _has_stream_links, _hoster_from_link, _is_aniworld_url, _is_internal_redirect_url, _language_from_id, _normalise_episode_path, _normalise_episode_text, _parse_episode_links, _parse_search_results, _parse_stream_link_buttons, _request_page, _resolve_html_redirect, _resolve_http_redirect, _search_title, _series_match_score, _series_slug, _should_find_matching_episode, _titles_match, episode_number, html_unescape |
| bsto.py | abweichend | 99.5% | 16311 | 16317 |  |
| burningseries.py | nur xShip |  |  |  |  |
| cineto.py | identisch | 100% |  |  |  |
| einschalten.py | abweichend | 21.5% | 7629 | 4215 |  \| xShip-only: _resolve_dood_default_tls |
| fhdfilme.py | abweichend | 93.7% | 3427 | 3486 |  |
| filmfans.py | identisch | 100% |  |  |  |
| filmo.py | abweichend | 55.3% | 21046 | 16424 | _external_url, _extract_redirect_url, _is_filmo_url, _redirect_target_from_response \| xShip-only: _dbg, _norm_title |
| filmpalast.py | abweichend | 4.5% | 4252 | 13342 | _absolute_url, _attr, _clean_text, _clean_title, _content_area, _episode_matches, _extract_year, _image_alt, _match_score, _next_page_urls, _parse_search_results, _parse_streams, _request, _search_candidates, _title_from_href, _title_variants, _year_matches \| xShip-only: chk_year |
| filmpro.py | abweichend | 99.1% | 3816 | 3829 |  |
| hdfilme.py | abweichend | 26.8% | 4127 | 3386 | parse_quality |
| huhu.py | abweichend | 6.1% | 4708 | 5449 | _request_json, _request_real_url, get_media_data, make_request, parse_hoster, parse_quality |
| internetarchive.py | nur xVault |  |  |  |  |
| kinoger.py | abweichend | 44.5% | 4692 | 12079 | _is_kinoger_resolver_host, _kinoger_resolver_source, _kinoger_resolver_url, _quali, _quality, _rewrite_dood, _url_host, aes, check_302, decodeStr, encodeStr, encodeUrl, get_embedurl, keys, makeid, toString |
| kinoking.py | nur xShip |  |  |  |  |
| kinokiste.py | abweichend | 8.6% | 4687 | 10365 | _getStreams, _isDirect, _languageFromWatch, _languageQueries, _parseQuality, _qualityRank, _request, _watchRequest |
| kinox.py | abweichend | 99.8% | 11076 | 11070 |  |
| kkiste.py | abweichend | 15.5% | 3598 | 9042 | _ajax_headers, _language_from_watch, _language_queries, _match_search_result, _request_json, _watch_json |
| kool.py | nur xShip |  |  |  |  |
| megakino.py | abweichend | 7.3% | 8186 | 5098 | _search_and_match, get_html, get_sources, get_url |
| meinecloud.py | nur xShip |  |  |  |  |
| moflix.py | abweichend | 7.7% | 6246 | 14913 | _add_videos, _best_match, _direct_hls_usable, _episode_videos, _first_child_playlist, _host_name, _info, _is_direct, _is_moflix_hls, _json, _language, _loose_title_match, _match_score, _mirror_priority, _quality, _request_text, _search_titles, _with_headers, _year |
| movie2k.py | abweichend | 20.1% | 4918 | 7145 | _ajax_headers, _language_from_watch, _language_queries, _match_search_result, _request_json, search \| xShip-only: _search |
| movie2k2.py | abweichend | 98.8% | 6284 | 6244 |  |
| movie4k.py | abweichend | 98.3% | 8655 | 8761 |  |
| moviedream.py | nur xShip |  |  |  |  |
| netzkino.py | abweichend | 16.2% | 2639 | 6002 | _build_graphql_search_url, _get_movie_details_by_id |
| nox.py | identisch | 100% |  |  |  |
| serienfans.py | identisch | 100% |  |  |  |
| serienstream.py | abweichend | 34.2% | 37896 | 38187 | _episode_chapter_number, _episode_title_tokens, _normalise_episode_text, _resolve_html_redirect, _series_match_score \| xShip-only: _do_login, _getLogin |
| streamcloud.py | abweichend | 93.9% | 3285 | 3374 |  |
| streamcloudforum.py | abweichend | 99.5% | 9932 | 9897 |  |
| topstreamfilm.py | abweichend | 94.0% | 3301 | 3391 |  |
| vavoo.py | nur xShip |  |  |  |  |
| vixstream.py | abweichend | 54.2% | 19186 | 19572 | _cleanup_hls_cache, _file_url, _hls_cache_dir, _key_uris_from_playlist, _local_hls_playlist_url, _request_bytes, _rewrite_hls_playlist, _rewrite_hls_uri_attr, repl \| xShip-only: _playlist_candidate |

## Zusammenfassung

- xShip Scraper: 34
- xVault Site-Scraper: 30
- Identisch: 4
- Abweichend: 24
- Nur xShip: 6
- Nur xVault: 2

Für jeden abweichenden gemeinsamen Scraper liegt unter `diffs/` ein Unified Diff.
