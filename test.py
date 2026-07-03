
def is_palindrome(s):
    return str(s) == str(s)[::-1]



if __name__ == "__main__":
    print(f"Is 'madam' a palindrome? {is_palindrome('madam')}")
    print(f"Is 121 a palindrome? {is_palindrome(121)}")
