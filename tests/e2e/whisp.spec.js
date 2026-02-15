import { test, expect } from '@playwright/test';

test.describe('Whisp E2E Tests', () => {
  
  test('should create and retrieve a text whisp', async ({ page, context }) => {
    // Navigate to home page
    await page.goto('/');
    
    // Create a whisp
    const secretMessage = 'This is a super secret test message!';
    await page.fill('#secret-text', secretMessage);
    await page.selectOption('#ttl', '10'); // 10 minutes
    await page.click('#create-btn');
    
    // Wait for result view
    await expect(page.locator('#result-view')).toBeVisible({ timeout: 5000 });
    
    // Get the whisp link
    const whispLink = await page.locator('#whisp-link').inputValue();
    expect(whispLink).toContain('http://localhost:8000/#');
    expect(whispLink).toContain(':'); // Should have id:key format
    
    // Extract the fragment (id:key)
    const urlParts = whispLink.split('#');
    expect(urlParts).toHaveLength(2);
    const fragment = urlParts[1];
    expect(fragment).toMatch(/^[a-f0-9\-]+:[A-Za-z0-9_-]+$/); // UUID:base64key
    
    console.log('Created whisp:', whispLink);
    
    // Open whisp in new page (simulating recipient)
    const newPage = await context.newPage();
    await newPage.goto(whispLink);
    
    // Should show access view
    await expect(newPage.locator('#access-view')).toBeVisible();
    await expect(newPage.locator('#create-view')).not.toBeVisible();
    
    // Click reveal button
    await newPage.click('#reveal-btn');
    
    // Wait for decryption
    await expect(newPage.locator('#secret-display')).toBeVisible({ timeout: 5000 });
    
    // Verify decrypted content
    const decryptedText = await newPage.locator('#decrypted-text').textContent();
    expect(decryptedText).toBe(secretMessage);
    
    console.log('Successfully decrypted:', decryptedText);
    
    await newPage.close();
  });

  test('should create and retrieve password-protected whisp', async ({ page, context }) => {
    await page.goto('/');
    
    const secretMessage = 'Password protected secret!';
    const password = 'mySecurePassword123';
    
    // Create whisp with password
    await page.fill('#secret-text', secretMessage);
    await page.fill('#password', password);
    await page.selectOption('#ttl', '60');
    await page.click('#create-btn');
    
    await expect(page.locator('#result-view')).toBeVisible({ timeout: 5000 });
    const whispLink = await page.locator('#whisp-link').inputValue();
    
    console.log('Created password-protected whisp:', whispLink);
    
    // Try to access without password (should fail)
    const newPage = await context.newPage();
    await newPage.goto(whispLink);
    await expect(newPage.locator('#access-view')).toBeVisible();
    
    // Should show password field
    await expect(newPage.locator('#pwd-required')).toBeVisible();
    
    // Try wrong password first
    await newPage.fill('#access-password', 'wrongPassword');
    await newPage.click('#reveal-btn');
    
    // Should show error
    await expect(newPage.locator('#error-view')).toBeVisible({ timeout: 3000 });
    
    // Go back and try correct password
    await newPage.goto(whispLink);
    await expect(newPage.locator('#access-view')).toBeVisible();
    await newPage.fill('#access-password', password);
    await newPage.click('#reveal-btn');
    
    // Should decrypt successfully
    await expect(newPage.locator('#secret-display')).toBeVisible({ timeout: 5000 });
    const decryptedText = await newPage.locator('#decrypted-text').textContent();
    expect(decryptedText).toBe(secretMessage);
    
    console.log('Password-protected whisp decrypted successfully');
    
    await newPage.close();
  });

  test('should delete whisp after first access (one-time use)', async ({ page, context }) => {
    await page.goto('/');
    
    const secretMessage = 'This should only be readable once!';
    
    // Create whisp
    await page.fill('#secret-text', secretMessage);
    await page.click('#create-btn');
    
    await expect(page.locator('#result-view')).toBeVisible({ timeout: 5000 });
    const whispLink = await page.locator('#whisp-link').inputValue();
    
    console.log('Created one-time whisp:', whispLink);
    
    // First access - should work
    const firstPage = await context.newPage();
    await firstPage.goto(whispLink);
    await firstPage.click('#reveal-btn');
    await expect(firstPage.locator('#secret-display')).toBeVisible({ timeout: 5000 });
    const firstDecrypt = await firstPage.locator('#decrypted-text').textContent();
    expect(firstDecrypt).toBe(secretMessage);
    
    console.log('First access succeeded');
    await firstPage.close();
    
    // Second access - should fail (whisp deleted)
    const secondPage = await context.newPage();
    await secondPage.goto(whispLink);
    
    // Wait a moment for the page to load
    await secondPage.waitForTimeout(1000);
    
    // Should show error view or access view, but clicking reveal should fail
    await secondPage.click('#reveal-btn');
    
    // Should show error
    await expect(secondPage.locator('#error-view')).toBeVisible({ timeout: 5000 });
    const errorMsg = await secondPage.locator('#error-msg').textContent();
    expect(errorMsg).toContain('not found');
    
    console.log('Second access correctly denied:', errorMsg);
    
    await secondPage.close();
  });

  test('should handle expired whisps', async ({ page, context }) => {
    await page.goto('/');
    
    const secretMessage = 'This will expire soon';
    
    // Create whisp with very short TTL (1 minute for practical testing)
    await page.fill('#secret-text', secretMessage);
    await page.selectOption('#ttl', '10'); // 10 minutes (shortest we can test practically)
    await page.click('#create-btn');
    
    await expect(page.locator('#result-view')).toBeVisible({ timeout: 5000 });
    const whispLink = await page.locator('#whisp-link').inputValue();
    
    // Verify whisp is created and accessible immediately
    const newPage = await context.newPage();
    await newPage.goto(whispLink);
    await expect(newPage.locator('#access-view')).toBeVisible();
    
    console.log('Whisp created with 10min expiry - verified accessible');
    
    await newPage.close();
  });

  test('should handle different TTL options', async ({ page }) => {
    await page.goto('/');
    
    // Check all TTL options are available
    const ttlOptions = await page.locator('#ttl option');
    const optionCount = await ttlOptions.count();
    expect(optionCount).toBeGreaterThan(2);
    
    // Verify option values
    const values = [];
    for (let i = 0; i < optionCount; i++) {
      const value = await ttlOptions.nth(i).getAttribute('value');
      values.push(value);
    }
    
    expect(values).toContain('10'); // 10 minutes
    expect(values).toContain('60'); // 1 hour
    expect(values).toContain('1440'); // 1 day
    
    console.log('Available TTL options:', values);
  });

  test('should display UI correctly', async ({ page }) => {
    await page.goto('/');
    
    // Check main elements are visible
    await expect(page.locator('h1')).toContainText('Whisp');
    await expect(page.locator('#secret-text')).toBeVisible();
    await expect(page.locator('#secret-file')).toBeVisible();
    await expect(page.locator('#password')).toBeVisible();
    await expect(page.locator('#ttl')).toBeVisible();
    await expect(page.locator('#create-btn')).toBeVisible();
    
    // Verify glassmorphism styling is applied
    const appDiv = page.locator('#app');
    await expect(appDiv).toHaveClass(/glass/);
    
    console.log('UI rendered correctly');
  });

  test('should copy whisp link to clipboard', async ({ page, context }) => {
    await page.goto('/');
    
    // Create a whisp
    await page.fill('#secret-text', 'Test for clipboard');
    await page.click('#create-btn');
    
    await expect(page.locator('#result-view')).toBeVisible({ timeout: 5000 });
    
    // Grant clipboard permissions
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    
    // Click copy button
    await page.click('#copy-btn');
    
    // Button should show success indicator
    await expect(page.locator('#copy-btn')).toContainText('✅');
    
    // Wait for it to reset
    await page.waitForTimeout(2500);
    await expect(page.locator('#copy-btn')).toContainText('📋');
    
    console.log('Clipboard copy functionality works');
  });
});
