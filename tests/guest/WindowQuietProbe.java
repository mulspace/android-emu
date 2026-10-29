import club.lang.resources.WindowQuiet;

public final class WindowQuietProbe {
    static class Fake implements WindowQuiet.Port {
        long time; int reads,pauses; boolean cancelled,late,regress,changing;
        String[] values={"old","new","new"};
        public long now(){return time;}
        public void alive()throws Exception{if(cancelled)throw new InterruptedException();}
        public String windows(){reads++;if(late)time+=9000;if(regress)time--;
            return changing?"window"+reads:values[Math.min(reads-1,values.length-1)];}
        public void pause(long ms){if(ms>100 || ms<=0)throw new AssertionError();time+=ms;pauses++;}
    }
    static void check(boolean ok){if(!ok)throw new AssertionError();}
    interface Action {void run()throws Exception;}
    static void fails(Class<?> type,Action action)throws Exception {
        try{action.run();throw new AssertionError("Accepted invalid transition");}
        catch(Exception error){check(type.isInstance(error));}
    }
    public static void main(String[] args)throws Exception {
        Fake a=new Fake();check(WindowQuiet.await(a,1000,8000)==1100);check(a.reads==12);
        Fake b=new Fake();b.values=new String[]{null,"", "new"};
        check(WindowQuiet.await(b,1000,8000)==1200);
        Fake c=new Fake();c.changing=true;
        fails(java.util.concurrent.TimeoutException.class,()->WindowQuiet.await(c,1000,8000));check(c.time==8000);
        Fake d=new Fake();d.late=true;
        fails(java.util.concurrent.TimeoutException.class,()->WindowQuiet.await(d,1000,8000));check(d.reads==1);
        Fake e=new Fake();e.cancelled=true;
        fails(InterruptedException.class,()->WindowQuiet.await(e,1000,8000));check(e.reads==0);
        Fake f=new Fake();f.regress=true;fails(IllegalStateException.class,()->WindowQuiet.await(f,1000,8000));
        for(long[] config:new long[][]{{0,8000},{1000,500},{2001,8000},{1000,10001}})
            fails(IllegalArgumentException.class,()->WindowQuiet.await(new Fake(),config[0],config[1]));
        System.out.println("Window quiet: 10 scenarios passed");
    }
}
