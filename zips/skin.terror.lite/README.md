# Terror-Lite Omega – Modded by Kusi

This folder stores installable ZIP packages for Kodi 21.2.

## Release 1.1.9

Upload the **binary** file named `skin.terror.lite-1.1.9.zip` into this folder using GitHub's **Add file → Upload files** action. It must contain `skin.terror.lite/addon.xml`, with the add-on ID `skin.terror.lite` and version `1.1.9`.

Once the upload is committed to `main`, the [skin publish workflow](../../.github/workflows/publish-terror-lite.yml) rebuilds `zips/addons.xml` and `zips/addons.xml.md5` automatically. Kodi then sees the skin under the existing Barclay Repository URL.

The upload is a ZIP of the confirmed Kodi Omega skin, not user-profile settings; widget and menu configuration inside Kodi is kept separately.
