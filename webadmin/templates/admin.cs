<?cs include "header.cs"?>
<?cs include "macros.cs"?>

<div id="content" class="admin">

 <h2>Trac Admin</h2>

  <ul class="vtabs"><?cs
    set:cur_cat = admin.pages.0.cat_id ?><?cs
    if admin.active_cat == cur_cat ?>
    <li class="active"><?cs var:admin.pages.0.cat_label?></li>
    <ul class="active"><?cs
    else ?>
    <li><?cs var:admin.pages.0.cat_label?></li>
    <ul><?cs
    /if ?><?cs
    each:page = admin.pages ?><?cs
    if cur_cat != page.cat_id ?><?cs
      set:cur_cat = page.cat_id ?>
    </ul><?cs
    if admin.active_cat == page.cat_id ?>
    <li class="active"><?cs var:page.cat_label ?></li>
    <ul class="active"><?cs
    else ?>
    <li><?cs var:page.cat_label ?></li>
    <ul><?cs
    /if ?><?cs /if ?><?cs
    if admin.active_cat == page.cat_id && admin.active_page == page.page_id ?>
      <li class="active"><a href="<?cs var:page.href ?>"><?cs 
          var:page.page_label ?></a></li><?cs
    else ?>
      <li><a href="<?cs var:page.href ?>"><?cs 
          var:page.page_label ?></a></li><?cs
    /if ?><?cs
    /each ?>
    </ul>
  </ul>
  <div class="tabcontents">
  <?cs include admin.page_template ?>
  </div>
</div>

<?cs include "footer.cs"?>
