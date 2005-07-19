<h2>Manage Plugins</h2>

<form id="addplug" class="addnew" method="post" enctype="multipart/form-data">
 <fieldset>
  <legend>Install Plugin:</legend>
  <div class="field">
   <label>File: <input type="file" name="egg_file" /></label>
  </div>
  <p class="help">Upload a plugin packaged as Python egg.</p>
  <div class="buttons">
   <input type="submit" name="install" value="Install">
  </div>
 </fieldset>
</form>

<script type="text/javascript" src="<?cs
  var:htdocs_location ?>js/admin.js"></script><?cs
 each:plugin = admin.plugins ?><form method="post"><div class="plugin">
 <h3 id="no<?cs var:name(plugin) ?>"><?cs
   var:plugin.name ?> <?cs var:plugin.version ?></h3>
 <div class="uninstall buttons">
  <input type="hidden" name="egg_filename" value="<?cs
    var:plugin.egg_filename ?>" />
  <input type="submit" value="Uninstall" name="uninstall" value="Uninstall"<?cs
   if:!plugin.egg_filename ?> disabled="disabled"<?cs /if ?> />
 </div>
 <table class="listing"><thead>
   <tr><th>Component</th><th class="sel">Enabled</th></tr>
  </thead><tbody><?cs
  each:component = plugin.components ?><tr>
   <td class="name" title="<?cs var:component.description ?>"><?cs
    var:component.name ?><p class="module"><?cs var:component.module ?></p></td>
   <td class="sel"><?cs
    if:!component.required ?><input type="hidden" name="component" value="<?cs
     var:component.module ?>.<?cs var:component.name ?>" /><?cs
    /if ?><input type="checkbox" name="enable" value="<?cs
     var:component.module ?>.<?cs var:component.name ?>"<?cs 
     if:component.enabled ?> checked="checked"<?cs
     /if ?><?cs
     if:component.required ?> disabled="disabled"<?cs
     /if ?> /></td>
  </tr><?cs
  /each ?></tbody>
 </table>
 <div class="update buttons">
  <input type="hidden" name="plugin" value="<?cs var:name(plugin) ?>" />
  <input type="submit" name="update" value="Apply changes" />
 </div></div><script type="text/javascript">
   enableFolding("no<?cs var:name(plugin) ?>");
 </script></form><?cs
 /each ?>
