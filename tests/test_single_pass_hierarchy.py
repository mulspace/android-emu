from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'JDK required')
class SinglePass(unittest.TestCase):
    def test_complete_walk_sensitivity_escaping_cancellation_and_recycling(self):
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / 'HierarchyProbe.java'
            probe.write_text(r'''
import club.lang.resources.SinglePassHierarchy;
import java.util.*;
public class HierarchyProbe {
 static void check(boolean v){if(!v)throw new AssertionError();}
 static class N implements SinglePassHierarchy.Node {
  List<N> children=new ArrayList<>(); boolean visible=true,password=false;int input=0,recycled=0,attrs=0,reads=0;
  String text="plain";
  public boolean visible(){return visible;} public boolean password(){return password;}
  public int inputType(){return input;} public int childCount(){return children.size();}
  public N child(int i){reads++;return children.get(i);} public void recycle(){recycled++;}
  public Map<String,String> attributes(){
   attrs++;Map<String,String> a=new HashMap<>();
   for(String k:new String[]{"checkable","checked","clickable","enabled","focusable","focused","scrollable","long-clickable","password","selected"})a.put(k,"false");
   a.put("text",text);a.put("resource-id","fixture:id/field");a.put("class","android.widget.TextView");a.put("package","fixture");
   a.put("content-desc",text);a.put("bounds","[0,0][10,10]");return a;
  }
 }
 static SinglePassHierarchy.Result run(N n)throws Exception{return SinglePassHierarchy.capture(Arrays.asList(n),0,()->{});}
 public static void main(String[] args)throws Exception {
  N root=new N(),child=new N();child.text="<tag> & \"quoted\"\n汉字😀";root.children.add(child);
  SinglePassHierarchy.Result result=run(root);check(result.nodeCount==2 && result.sensitive.isEmpty());
  check(root.reads==1 && child.recycled==1 && root.recycled==0 && root.attrs==1 && child.attrs==1);
  org.w3c.dom.Document parsed=javax.xml.parsers.DocumentBuilderFactory.newInstance().newDocumentBuilder()
   .parse(new java.io.ByteArrayInputStream(result.xml.getBytes("UTF-8")));
  check(((org.w3c.dom.Element)parsed.getElementsByTagName("node").item(1)).getAttribute("text").equals(child.text));
  for(int type:new int[]{129,145,225,18}) {
   N a=new N(),hidden=new N(),secret=new N();hidden.visible=false;secret.input=type;secret.text="PRIVATE-PASSWORD";
   a.children.add(hidden);hidden.children.add(secret);result=run(a);
   check(result.sensitive.size()==1 && result.nodeCount==3 && !result.xml.contains("PRIVATE-PASSWORD"));
   check(hidden.recycled==1 && secret.recycled==1);
  }
  N secret=new N();secret.password=true;secret.text="PRIVATE-SECRET";result=run(secret);
  check(result.sensitive.size()==1 && !result.xml.contains("PRIVATE-SECRET"));
  N missing=new N(),good=new N();missing.children.add(good);missing.children.add(null);
  try {run(missing);throw new AssertionError();}catch(SinglePassHierarchy.IncompleteHierarchy expected){check(expected.depth==1 && expected.index==1 && expected.visited==2);}
  check(good.recycled==1);
  N deep=new N(),tail=deep;for(int i=0;i<81;i++){N n=new N();tail.children.add(n);tail=n;}
  try {run(deep);throw new AssertionError();}catch(IllegalStateException expected){}
  check(tail.recycled==1);
  N cancelled=new N(),leaf=new N();cancelled.children.add(leaf);final int[] calls={0};
  try {SinglePassHierarchy.capture(Arrays.asList(cancelled),0,()->{if(++calls[0]==3)throw new Exception("cancelled");});throw new AssertionError();}
  catch(Exception expected){check(expected.getMessage().equals("cancelled"));}check(leaf.recycled==1);
  N invalid=new N();invalid.text="\u0001";
  try {run(invalid);throw new AssertionError();}catch(IllegalStateException expected){}
  N large=new N();large.text=new String(new char[1000001]).replace('\0','a');
  try {run(large);throw new AssertionError();}catch(IllegalStateException expected){}
 }
}
''')
            source = ROOT / 'experimental/native/SinglePassHierarchy.java'
            subprocess.run(['javac', '-d', tmp, str(source), str(probe)], check=True, timeout=30)
            subprocess.run(['java', '-cp', tmp, 'HierarchyProbe'], check=True, timeout=15)


if __name__ == '__main__':
    unittest.main()
