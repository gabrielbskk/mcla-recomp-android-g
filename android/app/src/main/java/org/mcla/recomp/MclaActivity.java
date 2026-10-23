package org.mcla.recomp;

import org.libsdl.app.SDLActivity;

/** SDL native gameplay activity. Assets are already imported into app-private filesDir/game. */
public final class MclaActivity extends SDLActivity {
    @Override protected String[] getLibraries() {
        return new String[] { "main" };
    }
}
