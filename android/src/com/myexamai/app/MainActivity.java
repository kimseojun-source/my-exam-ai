package com.myexamai.app;

import android.app.Activity;
import android.Manifest;
import android.app.DownloadManager;
import android.content.pm.PackageManager;
import android.content.Intent;
import android.content.res.Configuration;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.Environment;
import android.view.View;
import android.webkit.*;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String ORIGIN="https://forest-v12-runtime-production.up.railway.app";
    private static final int PICK_FILE=41;
    private static final int MIC_PERMISSION=42;
    private WebView web;
    private ValueCallback<Uri[]> files;
    private PermissionRequest microphoneRequest;
    private boolean internal(Uri uri) {
        return "https".equals(uri.getScheme()) && Uri.parse(ORIGIN).getHost().equals(uri.getHost()) && (uri.getPort()==-1 || uri.getPort()==443);
    }
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        web=new WebView(this);web.setBackgroundColor(Color.rgb(245,247,241));setContentView(web);
        // Android 15 edge-to-edge: keep content clear of status/navigation bars and IME.
        web.setOnApplyWindowInsetsListener((view,insets)->{
            if(android.os.Build.VERSION.SDK_INT>=30){
                android.graphics.Insets bars=insets.getInsets(android.view.WindowInsets.Type.systemBars()|android.view.WindowInsets.Type.displayCutout()|android.view.WindowInsets.Type.ime());
                view.setPadding(bars.left,bars.top,bars.right,bars.bottom);
            } else {view.setPadding(insets.getSystemWindowInsetLeft(),insets.getSystemWindowInsetTop(),insets.getSystemWindowInsetRight(),insets.getSystemWindowInsetBottom());}
            return insets;
        });
        WebSettings settings=web.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);
        settings.setUseWideViewPort(true);settings.setLoadWithOverviewMode(false);settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(true);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        CookieManager.getInstance().setAcceptCookie(true);
        web.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){
                Uri uri=request.getUrl();if(internal(uri))return false;
                if("https".equals(uri.getScheme())||"http".equals(uri.getScheme())||"mailto".equals(uri.getScheme())){
                    try{startActivity(new Intent(Intent.ACTION_VIEW,uri));}catch(Exception e){Toast.makeText(MainActivity.this,"링크를 열 앱이 없어.",Toast.LENGTH_SHORT).show();}
                }
                return true;
            }
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){
                if(request.isForMainFrame())Toast.makeText(MainActivity.this,"인터넷 연결을 확인하고 다시 열어줘.",Toast.LENGTH_LONG).show();
            }
            // Default SSL errors are cancelled. Never bypass certificate validation.
        });
        web.setWebChromeClient(new WebChromeClient(){
            @Override public void onPermissionRequest(PermissionRequest request){
                runOnUiThread(()->{
                    if(!internal(request.getOrigin()) || request.getResources().length!=1 || !PermissionRequest.RESOURCE_AUDIO_CAPTURE.equals(request.getResources()[0])){request.deny();return;}
                    if(android.os.Build.VERSION.SDK_INT<23 || checkSelfPermission(Manifest.permission.RECORD_AUDIO)==PackageManager.PERMISSION_GRANTED){request.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});return;}
                    if(microphoneRequest!=null)microphoneRequest.deny();microphoneRequest=request;requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO},MIC_PERMISSION);
                });
            }
            @Override public void onPermissionRequestCanceled(PermissionRequest request){if(microphoneRequest==request)microphoneRequest=null;}
            @Override public boolean onShowFileChooser(WebView view,ValueCallback<Uri[]> callback,FileChooserParams params){
                if(files!=null)files.onReceiveValue(null);files=callback;
                Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.addCategory(Intent.CATEGORY_OPENABLE);intent.setType("*/*");
                intent.putExtra(Intent.EXTRA_MIME_TYPES,new String[]{"application/pdf","image/*"});
                intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE,params.getMode()==FileChooserParams.MODE_OPEN_MULTIPLE);
                try{startActivityForResult(intent,PICK_FILE);return true;}catch(Exception e){files.onReceiveValue(null);files=null;return true;}
            }
        });
        web.setDownloadListener((url,userAgent,disposition,mime,length)->{
            Uri uri=Uri.parse(url);if(!internal(uri))return;
            String filename=URLUtil.guessFileName(url,disposition,mime);
            DownloadManager.Request request=new DownloadManager.Request(uri);
            String cookies=CookieManager.getInstance().getCookie(ORIGIN);if(cookies!=null)request.addRequestHeader("Cookie",cookies);
            request.addRequestHeader("User-Agent",userAgent);request.setMimeType(mime);
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED);
            request.setDestinationInExternalFilesDir(MainActivity.this,Environment.DIRECTORY_DOWNLOADS,filename);
            try{((DownloadManager)getSystemService(DOWNLOAD_SERVICE)).enqueue(request);Toast.makeText(MainActivity.this,"다운로드를 시작했어.",Toast.LENGTH_SHORT).show();}
            catch(Exception e){Toast.makeText(MainActivity.this,"다운로드를 시작하지 못했어.",Toast.LENGTH_LONG).show();}
        });
        if(state==null || web.restoreState(state)==null)web.loadUrl(ORIGIN);
    }
    @Override protected void onActivityResult(int code,int result,Intent data){
        super.onActivityResult(code,result,data);
        if(code==PICK_FILE && files!=null){
            Uri[] resultUris=null;
            if(result==RESULT_OK && data!=null){
                if(data.getClipData()!=null){resultUris=new Uri[data.getClipData().getItemCount()];for(int i=0;i<resultUris.length;i++)resultUris[i]=data.getClipData().getItemAt(i).getUri();}
                else if(data.getData()!=null)resultUris=new Uri[]{data.getData()};
            }
            files.onReceiveValue(resultUris);files=null;
        }
    }
    @Override public void onRequestPermissionsResult(int code,String[] permissions,int[] results){
        super.onRequestPermissionsResult(code,permissions,results);
        if(code==MIC_PERMISSION && microphoneRequest!=null){
            if(results.length>0 && results[0]==PackageManager.PERMISSION_GRANTED)microphoneRequest.grant(new String[]{PermissionRequest.RESOURCE_AUDIO_CAPTURE});
            else microphoneRequest.deny();
            microphoneRequest=null;
        }
    }
    @Override public void onConfigurationChanged(Configuration config){super.onConfigurationChanged(config);web.requestLayout();}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);web.saveState(state);}
    @Override protected void onPause(){CookieManager.getInstance().flush();super.onPause();}
    @Override public void onBackPressed(){if(web.canGoBack())web.goBack();else super.onBackPressed();}
    @Override protected void onDestroy(){if(files!=null)files.onReceiveValue(null);if(microphoneRequest!=null){microphoneRequest.deny();microphoneRequest=null;}web.destroy();super.onDestroy();}
}
