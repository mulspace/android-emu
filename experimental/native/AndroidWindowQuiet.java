package club.lang.resources;

import android.app.UiAutomation;
import android.graphics.Rect;
import android.os.SystemClock;
import android.view.accessibility.AccessibilityWindowInfo;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** No root or child requests while windows are moving; full capture follows. */
public final class AndroidWindowQuiet {
    private AndroidWindowQuiet() {}
    public interface Check { void alive() throws Exception; }
    public static long await(UiAutomation automation,Check check) throws Exception {
        return WindowQuiet.await(new WindowQuiet.Port() {
            public long now(){return SystemClock.elapsedRealtime();}
            public void alive()throws Exception{check.alive();}
            public void pause(long ms)throws Exception{SystemClock.sleep(ms);check.alive();}
            public String windows()throws Exception {
                List<AccessibilityWindowInfo> windows=automation.getWindows();
                if(windows==null)return null;
                try {
                    if(windows.size()>32)throw new IllegalStateException();
                    List<String> rows=new ArrayList<>();
                    int active=0,focused=0;
                    for(AccessibilityWindowInfo window:windows) {
                        check.alive();
                        if(window==null)throw new IllegalStateException();
                        Rect bounds=new Rect();window.getBoundsInScreen(bounds);
                        if(window.isActive())active++;
                        if(window.isFocused())focused++;
                        rows.add(window.getId()+":"+window.getType()+":"+window.getLayer()
                            +":"+window.isActive()+":"+window.isFocused()+":"+bounds.toShortString());
                    }
                    if(active!=1 || focused!=1)return null;
                    Collections.sort(rows);
                    return rows.toString();
                } finally {for(AccessibilityWindowInfo window:windows)if(window!=null)window.recycle();}
            }
        },1000,8000);
    }
}
